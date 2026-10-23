//! SQLite e a unica fonte de verdade do trabalho progressivo (T02).
//! Nenhum resultado de comando e publicado antes de COMMIT. Tempo civil e apenas diagnostico.
use crate::clock::{Clock, ClockSample};
use anyhow::{anyhow, bail, Context, Result};
use chrono::{SecondsFormat, TimeZone, Utc};
use rusqlite::{params, Connection, OptionalExtension, Transaction, TransactionBehavior};
use std::collections::HashMap;
use std::path::Path;
use std::time::Duration;
use uuid::Uuid;

const INITIAL_SQL: &str = include_str!("../../migrations/0001_initial.sql");

fn stamp(now: ClockSample) -> Result<String> {
    Ok(Utc
        .timestamp_millis_opt(now.utc_ms)
        .single()
        .ok_or_else(|| anyhow!("instante UTC fora do intervalo"))?
        .to_rfc3339_opts(SecondsFormat::Millis, true))
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Metrics {
    pub own_elapsed_ms: u64,
    pub task_time_ms: u64,
    pub running_task_count: u64,
}
#[derive(Clone, Copy)]
struct Anchor {
    awake_ms: u64,
    confirmed_ms: u64,
}

#[derive(Debug, Clone)]
pub struct ProjectRow {
    pub id: String,
    pub name: String,
}
#[derive(Debug, Clone)]
pub struct TaskRow {
    pub id: String,
    pub project_id: String,
    pub name: String,
    pub status: String,
}

pub struct WorkRepository<C: Clock> {
    conn: Connection,
    clock: C,
    // Chaves de entrada e intervalo de projeto. O monotonic nunca e persistido.
    entries: HashMap<String, Anchor>,
    intervals: HashMap<String, Anchor>,
    fail_next_commit: bool,
}

impl<C: Clock> WorkRepository<C> {
    pub fn open(path: impl AsRef<Path>, clock: C) -> Result<Self> {
        let path = path.as_ref();
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        let mut conn = Connection::open(path).context("abrir SQLite")?;
        conn.pragma_update(None, "foreign_keys", "ON")?;
        conn.busy_timeout(Duration::from_millis(5000))?;
        conn.pragma_update(None, "journal_mode", "WAL")?;
        conn.pragma_update(None, "synchronous", "FULL")?;
        let integrity: String = conn.query_row("PRAGMA quick_check", [], |r| r.get(0))?;
        if integrity != "ok" {
            bail!("integridade SQLite falhou: {integrity}");
        }
        Self::apply_initial_migration(&mut conn, clock.sample())?;
        Self::recover_interrupted(&mut conn)?;
        let mut repo = Self {
            conn,
            clock,
            entries: HashMap::new(),
            intervals: HashMap::new(),
            fail_next_commit: false,
        };
        // Boot nao retoma trabalho interrompido automaticamente.
        let awake = repo.clock.sample().awake_ms;
        repo.refresh_anchors(awake)?;
        Ok(repo)
    }

    fn apply_initial_migration(conn: &mut Connection, now: ClockSample) -> Result<()> {
        let version: i64 = conn.pragma_query_value(None, "user_version", |r| r.get(0))?;
        if version > 1 {
            bail!("schema SQLite futuro nao suportado: {version}");
        }
        if version == 0 {
            // Nao interpretar arquivo preexistente desconhecido como banco vazio.
            let tables: i64 = conn.query_row("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'", [], |r| r.get(0))?;
            if tables != 0 {
                bail!("banco sem versao com tabelas existentes; nao reescrever");
            }
            let tx = conn.transaction_with_behavior(TransactionBehavior::Immediate)?;
            tx.execute_batch(INITIAL_SQL)?;
            tx.execute("INSERT INTO schema_migrations(version,name,applied_at_utc) VALUES (1,'0001_initial.sql',?1)", [stamp(now)?])?;
            tx.pragma_update(None, "user_version", 1)?;
            tx.commit()?;
        }
        let registered: i64 = conn.query_row(
            "SELECT count(*) FROM schema_migrations WHERE version=1 AND name='0001_initial.sql'",
            [],
            |r| r.get(0),
        )?;
        if registered != 1 {
            bail!("migration 0001 inconsistente");
        }
        let foreign_keys: i64 = conn.pragma_query_value(None, "foreign_keys", |r| r.get(0))?;
        if foreign_keys != 1 {
            bail!("foreign_keys desativado");
        }
        let mut statement = conn.prepare("PRAGMA foreign_key_check")?;
        if statement.query([])?.next()?.is_some() {
            bail!("relacoes SQLite invalidas");
        }
        Ok(())
    }

    fn recover_interrupted(conn: &mut Connection) -> Result<()> {
        let tx = conn.transaction_with_behavior(TransactionBehavior::Immediate)?;
        tx.execute("UPDATE time_entries SET status='interrupted',closed_at_utc=checkpoint_at_utc WHERE status='running'", [])?;
        tx.execute("UPDATE project_activity_intervals SET status='interrupted',closed_at_utc=checkpoint_at_utc WHERE status='running'", [])?;
        tx.execute(
            "UPDATE tasks SET status='paused' WHERE status='running'",
            [],
        )?;
        tx.commit()?;
        Ok(())
    }

    fn refresh_anchors(&mut self, awake_ms: u64) -> Result<()> {
        self.entries.clear();
        self.intervals.clear();
        for (sql, dest) in [
            (
                "SELECT id,confirmed_ms FROM time_entries WHERE status='running'",
                &mut self.entries,
            ),
            (
                "SELECT id,confirmed_ms FROM project_activity_intervals WHERE status='running'",
                &mut self.intervals,
            ),
        ] {
            let mut stmt = self.conn.prepare(sql)?;
            for row in stmt.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, u64>(1)?)))? {
                let (id, confirmed_ms) = row?;
                dest.insert(
                    id,
                    Anchor {
                        awake_ms,
                        confirmed_ms,
                    },
                );
            }
        }
        Ok(())
    }

    fn project_exists(tx: &Transaction<'_>, project_id: &str) -> Result<()> {
        let status: Option<Option<String>> = tx
            .query_row(
                "SELECT archived_at_utc FROM projects WHERE id=?1",
                [project_id],
                |r| r.get(0),
            )
            .optional()?;
        match status {
            None => bail!("projeto inexistente"),
            Some(Some(_)) => bail!("projeto arquivado"),
            Some(None) => Ok(()),
        }
    }

    fn flush_rows(
        tx: &Transaction<'_>,
        table: &str,
        anchors: &HashMap<String, Anchor>,
        now: ClockSample,
    ) -> Result<()> {
        // table e uma constante interna, nunca entrada de usuario.
        let sql=format!("UPDATE {table} SET confirmed_ms=?1,checkpoint_at_utc=?2 WHERE id=?3 AND status='running'");
        let now_stamp = stamp(now)?;
        for (id, a) in anchors {
            let delta = now
                .awake_ms
                .checked_sub(a.awake_ms)
                .ok_or_else(|| anyhow!("relógio monotônico retrocedeu"))?;
            let total = a
                .confirmed_ms
                .checked_add(delta)
                .ok_or_else(|| anyhow!("overflow de tempo"))?;
            if tx.execute(&sql, params![i64::try_from(total)?, now_stamp, id])? != 1 {
                bail!("sessao aberta incoerente: {id}");
            }
        }
        Ok(())
    }
    fn flush(
        tx: &Transaction<'_>,
        entries: &HashMap<String, Anchor>,
        intervals: &HashMap<String, Anchor>,
        now: ClockSample,
    ) -> Result<()> {
        Self::flush_rows(tx, "time_entries", entries, now)?;
        Self::flush_rows(tx, "project_activity_intervals", intervals, now)
    }
    // Injetar falha em testes locais, nunca como flag de runtime ou persistencia.
    pub fn fail_once_before_commit(&mut self) {
        self.fail_next_commit = true;
    }

    pub fn create_project(&mut self, name: &str) -> Result<String> {
        if name.trim().is_empty() {
            bail!("nome de projeto obrigatorio");
        }
        let id = Uuid::new_v4().to_string();
        let now = self.clock.sample();
        let t = stamp(now)?;
        let tx = self
            .conn
            .transaction_with_behavior(TransactionBehavior::Immediate)?;
        tx.execute(
            "INSERT INTO projects(id,name,created_at_utc,updated_at_utc) VALUES (?1,?2,?3,?3)",
            params![id, name, t],
        )?;
        // create_project nao cria ancora, mas precisa preservar rollback em falha.
        if self.fail_next_commit {
            self.fail_next_commit = false;
            bail!("falha injetada antes do COMMIT");
        }
        tx.commit()?;
        Ok(id)
    }
    pub fn create_task(&mut self, project_id: &str, name: &str) -> Result<String> {
        if name.trim().is_empty() {
            bail!("nome de tarefa obrigatorio");
        }
        let id = Uuid::new_v4().to_string();
        let now = self.clock.sample();
        let t = stamp(now)?;
        let tx = self
            .conn
            .transaction_with_behavior(TransactionBehavior::Immediate)?;
        Self::project_exists(&tx, project_id)?;
        tx.execute("INSERT INTO tasks(id,project_id,name,status,created_at_utc,updated_at_utc) VALUES (?1,?2,?3,'stopped',?4,?4)",params![id,project_id,name,t])?;
        if self.fail_next_commit {
            self.fail_next_commit = false;
            bail!("falha injetada antes do COMMIT");
        }
        tx.commit()?;
        Ok(id)
    }
    pub fn transition(&mut self, task_id: &str, command: &str) -> Result<()> {
        let now = self.clock.sample();
        let t = stamp(now)?;
        let tx = self
            .conn
            .transaction_with_behavior(TransactionBehavior::Immediate)?;
        let current: Option<(String, String)> = tx
            .query_row(
                "SELECT project_id,status FROM tasks WHERE id=?1",
                [task_id],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .optional()?;
        let (project_id, state) = current.ok_or_else(|| anyhow!("tarefa nao encontrada"))?;
        let count: i64 = tx.query_row(
            "SELECT COUNT(*) FROM tasks WHERE project_id=?1 AND status='running'",
            [&project_id],
            |r| r.get(0),
        )?;
        match (command, state.as_str()) {
            ("start", "stopped") | ("resume", "paused") => {
                Self::project_exists(&tx, &project_id)?;
                Self::flush(&tx, &self.entries, &self.intervals, now)?;
                if count == 0 {
                    tx.execute("INSERT INTO project_activity_intervals(id,project_id,started_at_utc,checkpoint_at_utc) VALUES (?1,?2,?3,?3)",params![Uuid::new_v4().to_string(),project_id,t])?;
                }
                tx.execute("INSERT INTO time_entries(id,task_id,started_at_utc,checkpoint_at_utc) VALUES (?1,?2,?3,?3)",params![Uuid::new_v4().to_string(),task_id,t])?;
                tx.execute(
                    "UPDATE tasks SET status='running',updated_at_utc=?1 WHERE id=?2",
                    params![t, task_id],
                )?;
            }
            ("pause", "running") | ("complete", "running") => {
                Self::flush(&tx, &self.entries, &self.intervals, now)?;
                tx.execute("UPDATE time_entries SET status='closed',closed_at_utc=?1 WHERE task_id=?2 AND status='running'",params![t,task_id])?;
                if count == 1 {
                    tx.execute("UPDATE project_activity_intervals SET status='closed',closed_at_utc=?1 WHERE project_id=?2 AND status='running'",params![t,project_id])?;
                }
                let target = if command == "pause" {
                    "paused"
                } else {
                    "completed"
                };
                tx.execute("UPDATE tasks SET status=?1,updated_at_utc=?2,completed_at_utc=CASE WHEN ?1='completed' THEN ?2 ELSE NULL END WHERE id=?3",params![target,t,task_id])?;
            }
            ("complete", "stopped" | "paused") => {
                tx.execute("UPDATE tasks SET status='completed',updated_at_utc=?1,completed_at_utc=?1 WHERE id=?2",params![t,task_id])?;
            }
            _ => bail!("transicao invalida: {command} em {state}"),
        }
        // drop(tx) acontece antes do retorno; nenhum estado interno e atualizado ao falhar.
        if self.fail_next_commit {
            self.fail_next_commit = false;
            bail!("falha injetada antes do COMMIT");
        }
        tx.commit()?;
        self.refresh_anchors(now.awake_ms)?;
        Ok(())
    }
    pub fn checkpoint(&mut self) -> Result<()> {
        let now = self.clock.sample();
        let tx = self
            .conn
            .transaction_with_behavior(TransactionBehavior::Immediate)?;
        Self::flush(&tx, &self.entries, &self.intervals, now)?;
        if self.fail_next_commit {
            self.fail_next_commit = false;
            bail!("falha injetada antes do COMMIT");
        }
        tx.commit()?;
        self.refresh_anchors(now.awake_ms)?;
        Ok(())
    }
    pub fn pause_all(&mut self) -> Result<usize> {
        let now = self.clock.sample();
        let t = stamp(now)?;
        let tx = self
            .conn
            .transaction_with_behavior(TransactionBehavior::Immediate)?;
        Self::flush(&tx, &self.entries, &self.intervals, now)?;
        let count = tx.execute(
            "UPDATE time_entries SET status='closed',closed_at_utc=?1 WHERE status='running'",
            [&t],
        )?;
        tx.execute("UPDATE project_activity_intervals SET status='closed',closed_at_utc=?1 WHERE status='running'",[&t])?;
        tx.execute(
            "UPDATE tasks SET status='paused',updated_at_utc=?1 WHERE status='running'",
            [&t],
        )?;
        if self.fail_next_commit {
            self.fail_next_commit = false;
            bail!("falha injetada antes do COMMIT");
        }
        tx.commit()?;
        self.refresh_anchors(now.awake_ms)?;
        Ok(count)
    }
    pub fn close_safely(&mut self) -> Result<()> {
        self.pause_all()?;
        Ok(())
    }

    pub fn project_metrics(&self, project_id: &str) -> Result<Metrics> {
        let now = self.clock.sample();
        let (own, task, running): (i64,i64,i64)=self.conn.query_row(
            "SELECT (SELECT COALESCE(SUM(confirmed_ms),0) FROM project_activity_intervals WHERE project_id=p.id),
                    (SELECT COALESCE(SUM(e.confirmed_ms),0) FROM time_entries e JOIN tasks t ON e.task_id=t.id WHERE t.project_id=p.id),
                    (SELECT COUNT(*) FROM tasks WHERE project_id=p.id AND status='running')
               FROM projects p WHERE p.id=?1",[project_id],|r|Ok((r.get(0)?,r.get(1)?,r.get(2)?)))?;
        let mut own_elapsed_ms = u64::try_from(own)?;
        let mut task_time_ms = u64::try_from(task)?;
        for (id, a) in &self.intervals {
            let parent: String = self.conn.query_row(
                "SELECT project_id FROM project_activity_intervals WHERE id=?1",
                [id],
                |r| r.get(0),
            )?;
            if parent == project_id {
                own_elapsed_ms = own_elapsed_ms
                    .checked_add(
                        now.awake_ms
                            .checked_sub(a.awake_ms)
                            .ok_or_else(|| anyhow!("monotonic reversed"))?,
                    )
                    .ok_or_else(|| anyhow!("overflow"))?;
            }
        }
        for (id, a) in &self.entries {
            let parent: String=self.conn.query_row("SELECT t.project_id FROM time_entries e JOIN tasks t ON e.task_id=t.id WHERE e.id=?1",[id],|r|r.get(0))?;
            if parent == project_id {
                task_time_ms = task_time_ms
                    .checked_add(
                        now.awake_ms
                            .checked_sub(a.awake_ms)
                            .ok_or_else(|| anyhow!("monotonic reversed"))?,
                    )
                    .ok_or_else(|| anyhow!("overflow"))?;
            }
        }
        Ok(Metrics {
            own_elapsed_ms,
            task_time_ms,
            running_task_count: u64::try_from(running)?,
        })
    }
    pub fn projects(&self) -> Result<Vec<ProjectRow>> {
        let mut stmt = self.conn.prepare(
            "SELECT id,name FROM projects WHERE archived_at_utc IS NULL ORDER BY created_at_utc,id",
        )?;
        let rows = stmt.query_map([], |r| {
            Ok(ProjectRow {
                id: r.get(0)?,
                name: r.get(1)?,
            })
        })?;
        Ok(rows.collect::<rusqlite::Result<Vec<_>>>()?)
    }
    pub fn tasks(&self, project_id: &str) -> Result<Vec<TaskRow>> {
        let mut stmt=self.conn.prepare("SELECT id,project_id,name,status FROM tasks WHERE project_id=?1 AND archived_at_utc IS NULL ORDER BY created_at_utc,id")?;
        let rows = stmt.query_map([project_id], |r| {
            Ok(TaskRow {
                id: r.get(0)?,
                project_id: r.get(1)?,
                name: r.get(2)?,
                status: r.get(3)?,
            })
        })?;
        Ok(rows.collect::<rusqlite::Result<Vec<_>>>()?)
    }
}

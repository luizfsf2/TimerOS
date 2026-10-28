use tempfile::tempdir;
use timeros_core::clock::FakeClock;
use timeros_core::persistence::json::{ConfigSnapshot, JsonStore};
use timeros_core::persistence::sqlite::WorkRepository;
const MIN: u64 = 60_000;
fn fixture() -> (tempfile::TempDir, FakeClock) {
    (tempdir().unwrap(), FakeClock::new(1_790_000_000_000, 0))
}

#[test]
fn migration_and_foreign_keys() {
    let (dir, clock) = fixture();
    let path = dir.path().join("timeros.db");
    let mut repo = WorkRepository::open(&path, clock).unwrap();
    assert!(repo.create_task("does-not-exist", "Orphan").is_err());
    let project = repo.create_project("P").unwrap();
    assert!(repo.create_task(&project, "T").is_ok());
    drop(repo);
    let db = rusqlite::Connection::open(path).unwrap();
    let v: i64 = db
        .pragma_query_value(None, "user_version", |r| r.get(0))
        .unwrap();
    assert_eq!(v, 1);
}
#[test]
fn overlap_60_120_and_checkpoint_idempotent() {
    let (dir, clock) = fixture();
    let mut repo = WorkRepository::open(dir.path().join("db"), clock.clone()).unwrap();
    let p = repo.create_project("P").unwrap();
    let a = repo.create_task(&p, "A").unwrap();
    let b = repo.create_task(&p, "B").unwrap();
    repo.transition(&a, "start").unwrap();
    repo.transition(&b, "start").unwrap();
    clock.advance_both_ms(MIN * 60);
    repo.checkpoint().unwrap();
    repo.checkpoint().unwrap();
    let m = repo.project_metrics(&p).unwrap();
    assert_eq!(
        (m.own_elapsed_ms, m.task_time_ms, m.running_task_count),
        (MIN * 60, MIN * 120, 2)
    );
    repo.transition(&a, "pause").unwrap();
    clock.advance_both_ms(MIN * 30);
    let m = repo.project_metrics(&p).unwrap();
    assert_eq!((m.own_elapsed_ms, m.task_time_ms), (MIN * 90, MIN * 150));
}
#[test]
fn rollback_not_acknowledged() {
    let (dir, clock) = fixture();
    let mut repo = WorkRepository::open(dir.path().join("db"), clock).unwrap();
    let p = repo.create_project("P").unwrap();
    let t = repo.create_task(&p, "T").unwrap();
    repo.fail_once_before_commit();
    assert!(repo.transition(&t, "start").is_err());
    assert_eq!(repo.tasks(&p).unwrap()[0].status, "stopped");
    assert_eq!(repo.project_metrics(&p).unwrap().running_task_count, 0);
}
#[test]
fn crash_restarts_paused_without_unconfirmed_time() {
    let (dir, clock) = fixture();
    let path = dir.path().join("db");
    let mut repo = WorkRepository::open(&path, clock.clone()).unwrap();
    let p = repo.create_project("P").unwrap();
    let t = repo.create_task(&p, "T").unwrap();
    repo.transition(&t, "start").unwrap();
    clock.advance_both_ms(MIN * 5);
    repo.checkpoint().unwrap();
    clock.advance_both_ms(MIN * 12);
    drop(repo);
    let repo = WorkRepository::open(&path, clock).unwrap();
    assert_eq!(repo.tasks(&p).unwrap()[0].status, "paused");
    let m = repo.project_metrics(&p).unwrap();
    assert_eq!((m.own_elapsed_ms, m.task_time_ms), (MIN * 5, MIN * 5));
}
#[test]
fn pause_resume_two_sessions() {
    let (dir, clock) = fixture();
    let path = dir.path().join("db");
    let mut repo = WorkRepository::open(&path, clock.clone()).unwrap();
    let p = repo.create_project("P").unwrap();
    let t = repo.create_task(&p, "T").unwrap();
    repo.transition(&t, "start").unwrap();
    clock.advance_both_ms(MIN);
    repo.transition(&t, "pause").unwrap();
    clock.advance_both_ms(MIN * 50);
    repo.transition(&t, "resume").unwrap();
    clock.advance_both_ms(MIN * 2);
    repo.close_safely().unwrap();
    drop(repo);
    let repo = WorkRepository::open(&path, clock).unwrap();
    assert_eq!(repo.tasks(&p).unwrap()[0].status, "paused");
    assert_eq!(repo.project_metrics(&p).unwrap().task_time_ms, MIN * 3);
    let db = rusqlite::Connection::open(path).unwrap();
    let cnt: i64 = db
        .query_row("SELECT count(*) FROM time_entries", [], |r| r.get(0))
        .unwrap();
    assert_eq!(cnt, 2);
}
#[test]
fn json_roundtrip_revision_backup_and_failure() {
    let (dir, _) = fixture();
    let mut store = JsonStore::open(dir.path()).unwrap();
    assert_eq!(store.state.revision, 0);
    let old = std::fs::read(dir.path().join("state.json")).unwrap();
    store.fail_once_before_replace();
    assert!(store
        .commit_state(0, store.state.clone(), "2026-10-21T01:00:00Z")
        .is_err());
    assert_eq!(store.state.revision, 0);
    assert_eq!(std::fs::read(dir.path().join("state.json")).unwrap(), old);
    store
        .commit_state(0, store.state.clone(), "2026-10-21T01:00:00Z")
        .unwrap();
    assert_eq!(store.state.revision, 1);
    assert_eq!(
        std::fs::read(dir.path().join("state.json.bak")).unwrap(),
        old
    );
    assert_eq!(JsonStore::open(dir.path()).unwrap().state.revision, 1);
}
#[test]
fn malformed_json_is_preserved() {
    let (dir, _) = fixture();
    drop(JsonStore::open(dir.path()).unwrap());
    let bad = b"{ certainly not JSON";
    std::fs::write(dir.path().join("config.json"), bad).unwrap();
    assert!(JsonStore::open(dir.path()).is_err());
    assert_eq!(std::fs::read(dir.path().join("config.json")).unwrap(), bad);
}
#[test]
fn stale_revision_and_unknown_envelope_rejected() {
    let (dir, _) = fixture();
    let mut store = JsonStore::open(dir.path()).unwrap();
    assert!(store
        .commit_config(9, ConfigSnapshot::default(), "2026-10-21T01:00:00Z")
        .is_err());
    let wrong = ConfigSnapshot {
        schema_version: 2,
        ..ConfigSnapshot::default()
    };
    assert!(store
        .commit_config(0, wrong, "2026-10-21T01:00:00Z")
        .is_err());
    drop(store);
    std::fs::write(dir.path().join("config.json"), r#"{"schema_version":99}"#).unwrap();
    assert!(JsonStore::open(dir.path()).is_err());
}

#[test]
fn explicit_restore_preserves_forensic_bytes() {
    let (dir, _) = fixture();
    let mut store = JsonStore::open(dir.path()).unwrap();
    store
        .commit_config(0, store.config.clone(), "2026-10-21T01:00:00Z")
        .unwrap();
    drop(store);
    let bad = b"{BROKEN";
    std::fs::write(dir.path().join("config.json"), bad).unwrap();
    assert!(
        timeros_core::persistence::json::restore_backup_explicit(dir.path(), "config", false)
            .is_err()
    );
    let copy = timeros_core::persistence::json::restore_backup_explicit(dir.path(), "config", true)
        .unwrap();
    assert_eq!(std::fs::read(copy).unwrap(), bad);
    assert!(JsonStore::open(dir.path()).is_ok());
}

#[test]
fn json_defaults_not_created_over_existing_database() {
    let (dir, _) = fixture();
    std::fs::write(dir.path().join("timeros.db"), b"preexisting").unwrap();
    assert!(JsonStore::open(dir.path()).is_err());
    assert!(!dir.path().join("config.json").exists());
    assert!(!dir.path().join("state.json").exists());
}

#[test]
fn json_fresh_install_with_instance_lock_file_is_allowed() {
    let (dir, _) = fixture();
    std::fs::write(dir.path().join(".timeros.lock"), b"").unwrap();
    let store = JsonStore::open(dir.path()).unwrap();
    assert_eq!(store.config.revision, 0);
    assert_eq!(store.state.revision, 0);
}

#[test]
fn json_stale_writer_cannot_overwrite_disk_revision() {
    let (dir, _) = fixture();
    let mut first = JsonStore::open(dir.path()).unwrap();
    let mut stale = JsonStore::open(dir.path()).unwrap();
    first
        .commit_config(0, first.config.clone(), "2026-10-21T01:00:00Z")
        .unwrap();
    let durable = std::fs::read(dir.path().join("config.json")).unwrap();
    assert!(stale
        .commit_config(0, stale.config.clone(), "2026-10-21T01:10:00Z")
        .is_err());
    assert_eq!(
        std::fs::read(dir.path().join("config.json")).unwrap(),
        durable
    );
    assert_eq!(stale.config.revision, 0);
}

#[test]
fn sqlite_open_entry_uniqueness_and_checks_are_enforced() {
    let (dir, clock) = fixture();
    let path = dir.path().join("db");
    let mut repo = WorkRepository::open(&path, clock).unwrap();
    let project_id = repo.create_project("P").unwrap();
    let task_id = repo.create_task(&project_id, "T").unwrap();
    repo.transition(&task_id, "start").unwrap();
    let db = rusqlite::Connection::open(path).unwrap();
    assert!(db
        .execute(
            "INSERT INTO time_entries (id, task_id, started_at_utc, checkpoint_at_utc) VALUES ('duplicate-open', ?1, '2026-10-21T01:00:00Z', '2026-10-21T01:00:00Z')",
            [&task_id],
        )
        .is_err());
    assert!(db
        .execute(
            "INSERT INTO projects (id, name, created_at_utc, updated_at_utc) VALUES ('blank', ' ', '2026-10-21T01:00:00Z', '2026-10-21T01:00:00Z')",
            [],
        )
        .is_err());
    assert!(db
        .execute("UPDATE tasks SET status='invalid' WHERE id=?1", [&task_id],)
        .is_err());
    assert!(db
        .execute(
            "UPDATE time_entries SET confirmed_ms=-1 WHERE task_id=?1",
            [&task_id],
        )
        .is_err());
}

#[test]
fn failed_checkpoint_preserves_monotonic_anchor_for_retry() {
    let (dir, clock) = fixture();
    let mut repo = WorkRepository::open(dir.path().join("db"), clock.clone()).unwrap();
    let project_id = repo.create_project("P").unwrap();
    let task_id = repo.create_task(&project_id, "T").unwrap();
    repo.transition(&task_id, "start").unwrap();
    clock.advance_both_ms(MIN * 5);
    repo.fail_once_before_commit();
    assert!(repo.checkpoint().is_err());
    clock.advance_both_ms(MIN * 2);
    repo.checkpoint().unwrap();
    let m = repo.project_metrics(&project_id).unwrap();
    assert_eq!((m.own_elapsed_ms, m.task_time_ms), (MIN * 7, MIN * 7));
}

#[test]
fn task_chronometer_counts_seconds_for_selected_task_only() {
    let (dir, clock) = fixture();
    let mut repo = WorkRepository::open(dir.path().join("timeros.db"), clock.clone()).unwrap();
    let project_id = repo.create_project("P").unwrap();
    let a = repo.create_task(&project_id, "A").unwrap();
    let b = repo.create_task(&project_id, "B").unwrap();
    assert_eq!(repo.task_elapsed_ms(&a).unwrap(), 0);
    repo.transition(&a, "start").unwrap();
    clock.advance_both_ms(12_000);
    assert_eq!(repo.task_elapsed_ms(&a).unwrap(), 12_000);
    assert_eq!(repo.task_elapsed_ms(&b).unwrap(), 0);
    repo.transition(&b, "start").unwrap();
    clock.advance_both_ms(3_000);
    assert_eq!(repo.task_elapsed_ms(&a).unwrap(), 15_000);
    assert_eq!(repo.task_elapsed_ms(&b).unwrap(), 3_000);
    repo.checkpoint().unwrap();
    assert_eq!(repo.task_elapsed_ms(&a).unwrap(), 15_000);
    repo.transition(&a, "pause").unwrap();
    clock.advance_both_ms(5_000);
    assert_eq!(repo.task_elapsed_ms(&a).unwrap(), 15_000);
    assert_eq!(repo.task_elapsed_ms(&b).unwrap(), 8_000);
}

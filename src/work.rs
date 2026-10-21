//! Trabalho progressivo em memoria. Persistencia transacional e recovery: I02.
//!
//! Tempo proprio do projeto e a uniao dos intervalos em que >=1 tarefa roda;
//! tempo atribuido e a soma independente das sessoes de cada tarefa.

use std::collections::BTreeMap;

use crate::clock::{Clock, ClockSample};
use crate::domain::{checked_delta, checked_sum, DomainError, ProjectId, TaskId, TimeEntryId};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProjectStatus { Active, Archived }

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TaskStatus { Stopped, Running, Paused, Completed }

#[derive(Debug, Clone)]
pub struct Project {
    pub id: ProjectId,
    pub name: String,
    pub status: ProjectStatus,
    own_confirmed_ms: u64,
    own_open_since_ms: Option<u64>,
}

#[derive(Debug, Clone)]
pub struct TimeEntry {
    pub id: TimeEntryId,
    pub task_id: TaskId,
    pub started_at_utc_ms: i64,
    pub started_awake_ms: u64,
    pub ended_at_utc_ms: Option<i64>,
    pub ended_awake_ms: Option<u64>,
    checkpoint_awake_ms: u64,
    confirmed_ms: u64,
}

impl TimeEntry {
    fn new(id: TimeEntryId, task_id: TaskId, now: ClockSample) -> Self {
        Self {
            id, task_id, started_at_utc_ms: now.utc_ms,
            started_awake_ms: now.awake_ms, ended_at_utc_ms: None,
            ended_awake_ms: None, checkpoint_awake_ms: now.awake_ms, confirmed_ms: 0,
        }
    }

    pub fn duration_ms(&self, awake_ms: u64) -> Result<u64, DomainError> {
        if self.ended_awake_ms.is_some() { return Ok(self.confirmed_ms); }
        checked_sum(self.confirmed_ms, checked_delta(awake_ms, self.checkpoint_awake_ms)?)
    }

    fn checkpoint(&mut self, awake_ms: u64) -> Result<(), DomainError> {
        let elapsed = checked_delta(awake_ms, self.checkpoint_awake_ms)?;
        self.confirmed_ms = checked_sum(self.confirmed_ms, elapsed)?;
        self.checkpoint_awake_ms = awake_ms;
        Ok(())
    }

    fn finish(&mut self, now: ClockSample) -> Result<(), DomainError> {
        if self.ended_awake_ms.is_some() { return Err(DomainError::InternalInvariant); }
        self.checkpoint(now.awake_ms)?;
        self.ended_awake_ms = Some(now.awake_ms);
        self.ended_at_utc_ms = Some(now.utc_ms);
        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct Task {
    pub id: TaskId,
    pub project_id: ProjectId,
    pub name: String,
    pub status: TaskStatus,
    entries: Vec<TimeEntry>,
}

impl Task {
    pub fn entries(&self) -> &[TimeEntry] { &self.entries }

    fn running_entry_mut(&mut self) -> Result<&mut TimeEntry, DomainError> {
        if self.status != TaskStatus::Running { return Err(DomainError::InvalidTaskTransition); }
        let entry = self.entries.last_mut().ok_or(DomainError::InternalInvariant)?;
        if entry.ended_awake_ms.is_some() { return Err(DomainError::InternalInvariant); }
        Ok(entry)
    }

    pub fn total_ms(&self, awake_ms: u64) -> Result<u64, DomainError> {
        self.entries.iter().try_fold(0_u64, |sum, e| checked_sum(sum, e.duration_ms(awake_ms)?))
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ProjectMetrics {
    pub own_elapsed_ms: u64,
    pub task_time_ms: u64,
    pub running_task_count: usize,
}

pub struct WorkCore<C: Clock> {
    clock: C,
    projects: BTreeMap<ProjectId, Project>,
    tasks: BTreeMap<TaskId, Task>,
    next_entry_id: u64,
    last_awake_ms: Option<u64>,
}

impl<C: Clock> WorkCore<C> {
    pub fn new(clock: C) -> Self {
        Self { clock, projects: BTreeMap::new(), tasks: BTreeMap::new(),
               next_entry_id: 1, last_awake_ms: None }
    }

    fn observe(&mut self) -> Result<ClockSample, DomainError> {
        let now = self.clock.sample();
        if self.last_awake_ms.is_some_and(|previous| now.awake_ms < previous) {
            return Err(DomainError::MonotonicClockReversed);
        }
        self.last_awake_ms = Some(now.awake_ms);
        Ok(now)
    }

    pub fn project(&self, id: ProjectId) -> Option<&Project> { self.projects.get(&id) }
    pub fn task(&self, id: TaskId) -> Option<&Task> { self.tasks.get(&id) }

    pub fn add_project(&mut self, id: ProjectId, name: impl Into<String>) -> Result<(), DomainError> {
        let name = name.into();
        if name.trim().is_empty() { return Err(DomainError::EmptyName); }
        if self.projects.contains_key(&id) { return Err(DomainError::DuplicateProject); }
        self.projects.insert(id, Project { id, name, status: ProjectStatus::Active,
            own_confirmed_ms: 0, own_open_since_ms: None });
        Ok(())
    }

    pub fn add_task(&mut self, id: TaskId, project_id: ProjectId, name: impl Into<String>) -> Result<(), DomainError> {
        let name = name.into();
        if name.trim().is_empty() { return Err(DomainError::EmptyName); }
        if self.tasks.contains_key(&id) { return Err(DomainError::DuplicateTask); }
        let project = self.projects.get(&project_id).ok_or(DomainError::ProjectNotFound)?;
        if project.status != ProjectStatus::Active { return Err(DomainError::ProjectArchived); }
        self.tasks.insert(id, Task { id, project_id, name, status: TaskStatus::Stopped, entries: Vec::new() });
        Ok(())
    }

    fn running_count(&self, project_id: ProjectId) -> usize {
        self.tasks.values().filter(|t| t.project_id == project_id && t.status == TaskStatus::Running).count()
    }

    fn begin_session(&mut self, id: TaskId, expected: TaskStatus) -> Result<(), DomainError> {
        let (project_id, state) = self.tasks.get(&id).map(|t|(t.project_id, t.status)).ok_or(DomainError::TaskNotFound)?;
        if state != expected { return Err(DomainError::InvalidTaskTransition); }
        if self.projects.get(&project_id).ok_or(DomainError::ProjectNotFound)?.status != ProjectStatus::Active {
            return Err(DomainError::ProjectArchived);
        }
        let now = self.observe()?;
        let entry_id = TimeEntryId::new(self.next_entry_id);
        let following = self.next_entry_id.checked_add(1).ok_or(DomainError::ArithmeticOverflow)?;
        if self.running_count(project_id) == 0 {
            let project = self.projects.get_mut(&project_id).ok_or(DomainError::ProjectNotFound)?;
            if project.own_open_since_ms.is_some() { return Err(DomainError::InternalInvariant); }
            project.own_open_since_ms = Some(now.awake_ms);
        }
        let task = self.tasks.get_mut(&id).ok_or(DomainError::TaskNotFound)?;
        task.entries.push(TimeEntry::new(entry_id, id, now));
        task.status = TaskStatus::Running;
        self.next_entry_id = following;
        Ok(())
    }

    pub fn start_task(&mut self, id: TaskId) -> Result<(), DomainError> {
        self.begin_session(id, TaskStatus::Stopped)
    }

    pub fn resume_task(&mut self, id: TaskId) -> Result<(), DomainError> {
        self.begin_session(id, TaskStatus::Paused)
    }

    fn finish_session(&mut self, id: TaskId, now: ClockSample, final_status: TaskStatus) -> Result<(), DomainError> {
        let project_id = self.tasks.get(&id).ok_or(DomainError::TaskNotFound)?.project_id;
        {
            let task = self.tasks.get_mut(&id).ok_or(DomainError::TaskNotFound)?;
            task.running_entry_mut()?.finish(now)?;
            task.status = final_status;
        }
        if self.running_count(project_id) == 0 {
            let project = self.projects.get_mut(&project_id).ok_or(DomainError::ProjectNotFound)?;
            let start = project.own_open_since_ms.ok_or(DomainError::InternalInvariant)?;
            project.own_confirmed_ms = checked_sum(project.own_confirmed_ms, checked_delta(now.awake_ms, start)?)?;
            project.own_open_since_ms = None;
        }
        Ok(())
    }

    pub fn pause_task(&mut self, id: TaskId) -> Result<(), DomainError> {
        if self.tasks.get(&id).ok_or(DomainError::TaskNotFound)?.status != TaskStatus::Running {
            return Err(DomainError::InvalidTaskTransition);
        }
        let now = self.observe()?;
        self.finish_session(id, now, TaskStatus::Paused)
    }

    pub fn complete_task(&mut self, id: TaskId) -> Result<(), DomainError> {
        let state = self.tasks.get(&id).ok_or(DomainError::TaskNotFound)?.status;
        if state == TaskStatus::Completed { return Err(DomainError::InvalidTaskTransition); }
        let now = self.observe()?;
        if state == TaskStatus::Running {
            self.finish_session(id, now, TaskStatus::Completed)
        } else {
            self.tasks.get_mut(&id).ok_or(DomainError::TaskNotFound)?.status = TaskStatus::Completed;
            Ok(())
        }
    }

    /// Avanca apenas a base interna. A confirmacao persistente pertence a I02.
    pub fn checkpoint_in_memory(&mut self) -> Result<(), DomainError> {
        let now = self.observe()?;
        for t in self.tasks.values_mut() {
            if t.status == TaskStatus::Running { t.running_entry_mut()?.checkpoint(now.awake_ms)?; }
        }
        for p in self.projects.values_mut() {
            if let Some(start) = p.own_open_since_ms {
                p.own_confirmed_ms = checked_sum(p.own_confirmed_ms, checked_delta(now.awake_ms, start)?)?;
                p.own_open_since_ms = Some(now.awake_ms);
            }
        }
        Ok(())
    }

    /// Usa uma unica amostra temporal para todos os recursos pausaveis de trabalho.
    pub fn pause_all_tasks(&mut self) -> Result<usize, DomainError> {
        let now = self.observe()?;
        let ids: Vec<_> = self.tasks.values().filter(|t| t.status == TaskStatus::Running).map(|t| t.id).collect();
        for id in &ids { self.finish_session(*id, now, TaskStatus::Paused)?; }
        Ok(ids.len())
    }

    pub fn archive_project(&mut self, id: ProjectId) -> Result<(), DomainError> {
        let p = self.projects.get(&id).ok_or(DomainError::ProjectNotFound)?;
        if self.running_count(id) > 0 || p.own_open_since_ms.is_some() {
            return Err(DomainError::InvalidTaskTransition);
        }
        self.projects.get_mut(&id).ok_or(DomainError::ProjectNotFound)?.status = ProjectStatus::Archived;
        Ok(())
    }

    pub fn task_elapsed_ms(&self, id: TaskId) -> Result<u64, DomainError> {
        let now = self.clock.sample();
        self.tasks.get(&id).ok_or(DomainError::TaskNotFound)?.total_ms(now.awake_ms)
    }

    pub fn project_metrics(&self, id: ProjectId) -> Result<ProjectMetrics, DomainError> {
        let now = self.clock.sample();
        let p = self.projects.get(&id).ok_or(DomainError::ProjectNotFound)?;
        let open_ms = p.own_open_since_ms.map(|start| checked_delta(now.awake_ms, start)).transpose()?.unwrap_or(0);
        let own_elapsed_ms = checked_sum(p.own_confirmed_ms, open_ms)?;
        let mut task_time_ms = 0;
        let mut running_task_count = 0;
        for task in self.tasks.values().filter(|t| t.project_id == id) {
            task_time_ms = checked_sum(task_time_ms, task.total_ms(now.awake_ms)?)?;
            if task.status == TaskStatus::Running { running_task_count += 1; }
        }
        Ok(ProjectMetrics { own_elapsed_ms, task_time_ms, running_task_count })
    }
}
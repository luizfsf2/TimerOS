-- TimerOS V1: migration 0001. Execute only in a disposable/local database via repository initialization.
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version > 0),
    name TEXT NOT NULL,
    applied_at_utc TEXT NOT NULL
);
CREATE TABLE projects (
    id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(id)) > 0),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    archived_at_utc TEXT
);
CREATE TABLE tasks (
    id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(id)) > 0),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    status TEXT NOT NULL DEFAULT 'stopped'
        CHECK (status IN ('stopped', 'running', 'paused', 'completed')),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    completed_at_utc TEXT,
    archived_at_utc TEXT,
    CHECK ((status = 'completed') = (completed_at_utc IS NOT NULL))
);
CREATE TABLE time_entries (
    id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(id)) > 0),
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
    started_at_utc TEXT NOT NULL,
    checkpoint_at_utc TEXT NOT NULL,
    closed_at_utc TEXT,
    confirmed_ms INTEGER NOT NULL DEFAULT 0 CHECK (confirmed_ms >= 0),
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'closed', 'interrupted')),
    CHECK (
      (status = 'running' AND closed_at_utc IS NULL)
      OR (status IN ('closed', 'interrupted') AND closed_at_utc IS NOT NULL)
    )
);
CREATE TABLE project_activity_intervals (
    id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(id)) > 0),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    started_at_utc TEXT NOT NULL,
    checkpoint_at_utc TEXT NOT NULL,
    closed_at_utc TEXT,
    confirmed_ms INTEGER NOT NULL DEFAULT 0 CHECK (confirmed_ms >= 0),
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status = 'running' AND closed_at_utc IS NULL
            OR status IN ('closed', 'interrupted') AND closed_at_utc IS NOT NULL)
);
CREATE INDEX idx_tasks_project_status ON tasks(project_id, status);
CREATE INDEX idx_time_entries_task_started ON time_entries(task_id, started_at_utc);
CREATE INDEX idx_project_activity_project_started
    ON project_activity_intervals(project_id, started_at_utc);
CREATE UNIQUE INDEX uq_time_entries_open_task
    ON time_entries(task_id) WHERE status = 'running';
CREATE UNIQUE INDEX uq_project_activity_open_project
    ON project_activity_intervals(project_id) WHERE status = 'running';
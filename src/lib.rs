//! Core independente de UI, banco, audio, arquivos e Win32.
//!
//! I01: invariantes e transicoes puras/em memoria. Os adaptadores SQLite/JSON e
//! a confirmacao de gravacao antes de publicar efeitos pertencem a I02/I05.
//! Nao existe scheduler/loop por timer neste crate.

pub mod clock;
pub mod countdown;
pub mod domain;
pub mod work;

pub use clock::{Clock, ClockSample, FakeClock};
pub use countdown::{CountdownDefinition, CountdownRun, CountdownState};
pub use domain::{
    AlertProfileId, CountdownId, CountdownRunId, DomainError, FixedAlarmId, FixedAlarmOccurrenceId,
    ProjectId, SequenceId, SequenceRunId, SoundId, TaskId, TimeEntryId,
};
pub use work::{ProjectMetrics, ProjectStatus, TaskStatus, WorkCore};

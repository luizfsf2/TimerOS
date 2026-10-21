//! Identidades opacas e erros de dominio. IDs definitivos persistidos: T02.

use core::fmt;

macro_rules! id_type {
    ($($name:ident),+ $(,)?) => {$ (
        #[derive(Debug, Copy, Clone, Eq, PartialEq, Hash, Ord, PartialOrd)]
        pub struct $name(u64);
        impl $name {
            pub const fn new(value: u64) -> Self { Self(value) }
            pub const fn get(self) -> u64 { self.0 }
        }
    )+};
}

id_type!(
    ProjectId,
    TaskId,
    TimeEntryId,
    CountdownId,
    CountdownRunId,
    FixedAlarmId,
    FixedAlarmOccurrenceId,
    SequenceId,
    SequenceRunId,
    AlertProfileId,
    SoundId,
);

#[derive(Debug, Copy, Clone, PartialEq, Eq)]
pub enum DomainError {
    EmptyName,
    ProjectNotFound,
    TaskNotFound,
    DuplicateProject,
    DuplicateTask,
    ProjectArchived,
    InvalidTaskTransition,
    InvalidCountdownTransition,
    InvalidDuration,
    MonotonicClockReversed,
    ArithmeticOverflow,
    InternalInvariant,
}

impl fmt::Display for DomainError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{}",
            match self {
                Self::EmptyName => "nome obrigatorio",
                Self::ProjectNotFound => "projeto nao encontrado",
                Self::TaskNotFound => "tarefa nao encontrada",
                Self::DuplicateProject => "identificador de projeto duplicado",
                Self::DuplicateTask => "identificador de tarefa duplicado",
                Self::ProjectArchived => "projeto arquivado",
                Self::InvalidTaskTransition => "transicao de tarefa invalida",
                Self::InvalidCountdownTransition => "transicao de countdown invalida",
                Self::InvalidDuration => "duracao invalida (deve ser positiva)",
                Self::MonotonicClockReversed => "relogio monotônico retrocedeu",
                Self::ArithmeticOverflow => "estouro de capacidade temporal",
                Self::InternalInvariant => "invariante interno violado",
            }
        )
    }
}

impl std::error::Error for DomainError {}

pub(crate) fn checked_delta(now: u64, earlier: u64) -> Result<u64, DomainError> {
    now.checked_sub(earlier)
        .ok_or(DomainError::MonotonicClockReversed)
}

pub(crate) fn checked_sum(a: u64, b: u64) -> Result<u64, DomainError> {
    a.checked_add(b).ok_or(DomainError::ArithmeticOverflow)
}

pub(crate) fn checked_due(utc_ms: i64, duration_ms: u64) -> Result<i64, DomainError> {
    let duration = i64::try_from(duration_ms).map_err(|_| DomainError::ArithmeticOverflow)?;
    utc_ms
        .checked_add(duration)
        .ok_or(DomainError::ArithmeticOverflow)
}

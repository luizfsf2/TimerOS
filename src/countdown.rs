//! FSM de um countdown generico e independente, sem scheduler nem persistencia.
//! Um `CountdownRun` ciclico tem no maximo uma pendencia; o proximo ciclo so
//! comeca apos reconhecimento explicito, nunca pela simples passagem do tempo.

use crate::clock::ClockSample;
use crate::domain::{checked_due, CountdownId, DomainError};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CountdownMode {
    OneShot,
    Cyclic,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CountdownDefinition {
    pub id: CountdownId,
    pub name: String,
    pub original_duration_ms: u64,
    pub mode: CountdownMode,
}

impl CountdownDefinition {
    pub fn new(
        id: CountdownId,
        name: impl Into<String>,
        original_duration_ms: u64,
        mode: CountdownMode,
    ) -> Result<Self, DomainError> {
        let name = name.into();
        if name.trim().is_empty() {
            return Err(DomainError::EmptyName);
        }
        if original_duration_ms == 0 {
            return Err(DomainError::InvalidDuration);
        }
        // Verifica cedo se pode ser somada ao tempo civil em milissegundos.
        i64::try_from(original_duration_ms).map_err(|_| DomainError::ArithmeticOverflow)?;
        Ok(Self {
            id,
            name,
            original_duration_ms,
            mode,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CountdownState {
    Stopped,
    Running { due_at_utc_ms: i64 },
    Paused { remaining_ms: u64 },
    Pending { due_at_utc_ms: i64 },
}

#[derive(Debug, Clone)]
pub struct CountdownRun {
    pub definition_snapshot: CountdownDefinition,
    pub generation: u64,
    state: CountdownState,
}

impl CountdownRun {
    pub fn new(definition: CountdownDefinition) -> Self {
        Self {
            definition_snapshot: definition,
            generation: 0,
            state: CountdownState::Stopped,
        }
    }

    pub fn state(&self) -> CountdownState {
        self.state
    }

    fn arm(&mut self, now: ClockSample, ms: u64, new_generation: bool) -> Result<(), DomainError> {
        let due = checked_due(now.utc_ms, ms)?;
        let next_generation = if new_generation {
            self.generation
                .checked_add(1)
                .ok_or(DomainError::ArithmeticOverflow)?
        } else {
            self.generation
        };
        self.generation = next_generation;
        self.state = CountdownState::Running { due_at_utc_ms: due };
        Ok(())
    }

    pub fn start(&mut self, now: ClockSample) -> Result<(), DomainError> {
        if self.state != CountdownState::Stopped {
            return Err(DomainError::InvalidCountdownTransition);
        }
        self.arm(now, self.definition_snapshot.original_duration_ms, true)
    }

    /// Idempotente: retorna true apenas na primeira passagem Running -> Pending.
    pub fn evaluate_due(&mut self, now: ClockSample) -> bool {
        if let CountdownState::Running { due_at_utc_ms: due } = self.state {
            if now.utc_ms >= due {
                self.state = CountdownState::Pending { due_at_utc_ms: due };
                return true;
            }
        }
        false
    }

    pub fn pause(&mut self, now: ClockSample) -> Result<(), DomainError> {
        self.evaluate_due(now);
        if let CountdownState::Running { due_at_utc_ms: due } = self.state {
            let remaining = u64::try_from(i128::from(due) - i128::from(now.utc_ms))
                .map_err(|_| DomainError::ArithmeticOverflow)?;
            self.state = CountdownState::Paused {
                remaining_ms: remaining,
            };
            Ok(())
        } else {
            Err(DomainError::InvalidCountdownTransition)
        }
    }

    pub fn resume(&mut self, now: ClockSample) -> Result<(), DomainError> {
        if let CountdownState::Paused { remaining_ms } = self.state {
            self.arm(now, remaining_ms, false)
        } else {
            Err(DomainError::InvalidCountdownTransition)
        }
    }

    pub fn stop(&mut self, now: ClockSample) -> Result<(), DomainError> {
        self.evaluate_due(now);
        match self.state {
            CountdownState::Running { .. } | CountdownState::Paused { .. } => {
                self.state = CountdownState::Stopped;
                Ok(())
            }
            _ => Err(DomainError::InvalidCountdownTransition),
        }
    }

    /// Reset individual sempre reinicia da duracao original e com nova geracao.
    pub fn reset(&mut self, now: ClockSample) -> Result<(), DomainError> {
        self.arm(now, self.definition_snapshot.original_duration_ms, true)
    }

    /// Adia a pendencia corrente, sem mudar a definicao nem gerar novo ciclo.
    pub fn snooze(&mut self, now: ClockSample, delay_ms: u64) -> Result<(), DomainError> {
        if delay_ms == 0 {
            return Err(DomainError::InvalidDuration);
        }
        self.evaluate_due(now);
        if !matches!(self.state, CountdownState::Pending { .. }) {
            return Err(DomainError::InvalidCountdownTransition);
        }
        self.arm(now, delay_ms, false)
    }

    pub fn acknowledge(&mut self, now: ClockSample) -> Result<(), DomainError> {
        self.evaluate_due(now);
        if !matches!(self.state, CountdownState::Pending { .. }) {
            return Err(DomainError::InvalidCountdownTransition);
        }
        match self.definition_snapshot.mode {
            CountdownMode::Cyclic => {
                self.arm(now, self.definition_snapshot.original_duration_ms, true)
            }
            CountdownMode::OneShot => {
                self.state = CountdownState::Stopped;
                Ok(())
            }
        }
    }

    /// Reset global: apenas ciclicos, deixando-os PARADOS.
    pub fn reset_day(&mut self) {
        if self.definition_snapshot.mode == CountdownMode::Cyclic {
            self.state = CountdownState::Stopped;
        }
    }

    pub fn remaining_ms(&self, now: ClockSample) -> Result<u64, DomainError> {
        match self.state {
            CountdownState::Stopped => Ok(self.definition_snapshot.original_duration_ms),
            CountdownState::Paused { remaining_ms } => Ok(remaining_ms),
            CountdownState::Running { due_at_utc_ms: due } => {
                if now.utc_ms >= due {
                    Ok(0)
                } else {
                    Ok(u64::try_from(i128::from(due) - i128::from(now.utc_ms))
                        .map_err(|_| DomainError::ArithmeticOverflow)?)
                }
            }
            CountdownState::Pending { .. } => Ok(0),
        }
    }
}

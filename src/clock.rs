//! Amostra simultanea de tempo civil UTC e referencia monotônica acordada.
//! O `awake_ms` vale apenas na vida de um processo e nunca deve ser persistido.

use std::cell::Cell;
use std::rc::Rc;

#[derive(Debug, Copy, Clone, Eq, PartialEq)]
pub struct ClockSample {
    pub utc_ms: i64,
    pub awake_ms: u64,
}

pub trait Clock {
    fn sample(&self) -> ClockSample;
}

/// FakeClock permite simular relogio civil, tempo acordado e suspensao separados.
#[derive(Clone, Debug)]
pub struct FakeClock {
    sample: Rc<Cell<ClockSample>>,
}

impl FakeClock {
    pub fn new(utc_ms: i64, awake_ms: u64) -> Self {
        Self { sample: Rc::new(Cell::new(ClockSample { utc_ms, awake_ms })) }
    }

    pub fn set_utc_ms(&self, utc_ms: i64) {
        let mut s = self.sample.get();
        s.utc_ms = utc_ms;
        self.sample.set(s);
    }

    /// Apenas para testes de deteccao de regressao monotônica.
    pub fn set_awake_ms(&self, awake_ms: u64) {
        let mut s = self.sample.get();
        s.awake_ms = awake_ms;
        self.sample.set(s);
    }

    /// Simula tempo acordado sem depender do relogio civil.
    pub fn advance_awake_ms(&self, ms: u64) {
        let mut s = self.sample.get();
        s.awake_ms = s.awake_ms.checked_add(ms).expect("fake clock: awake overflow");
        self.sample.set(s);
    }

    /// Simula ajuste de hora civil ou passagem do tempo durante suspensao.
    pub fn advance_wall_ms(&self, ms: i64) {
        let mut s = self.sample.get();
        s.utc_ms = s.utc_ms.checked_add(ms).expect("fake clock: wall overflow");
        self.sample.set(s);
    }

    pub fn advance_both_ms(&self, ms: u64) {
        let civil = i64::try_from(ms).expect("fake clock: duration out of range");
        let mut s = self.sample.get();
        s.utc_ms = s.utc_ms.checked_add(civil).expect("fake clock: wall overflow");
        s.awake_ms = s.awake_ms.checked_add(ms).expect("fake clock: awake overflow");
        self.sample.set(s);
    }
}

impl Clock for FakeClock {
    fn sample(&self) -> ClockSample { self.sample.get() }
}
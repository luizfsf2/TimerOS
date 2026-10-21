//! Adaptador do relogio para runtime (FakeClock segue reservado para testes).
use crate::clock::{Clock, ClockSample};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

pub struct SystemClock {
    started: Instant,
}
impl Default for SystemClock {
    fn default() -> Self { Self::new() }
}
impl SystemClock {
    pub fn new() -> Self { Self { started: Instant::now() } }
}
impl Clock for SystemClock {
    fn sample(&self) -> ClockSample {
        let utc_ms = SystemTime::now().duration_since(UNIX_EPOCH)
            .expect("relógio civil anterior a 1970").as_millis() as i64;
        let awake_ms = self.started.elapsed().as_millis() as u64;
        ClockSample { utc_ms, awake_ms }
    }
}
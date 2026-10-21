use timeros_core::{
    Clock, CountdownDefinition, CountdownId, CountdownRun, CountdownState,
    DomainError, FakeClock, ProjectId, TaskId, TaskStatus, WorkCore,
};
use timeros_core::countdown::CountdownMode;

const M: u64 = 60_000;
fn project(n: u64) -> ProjectId { ProjectId::new(n) }
fn task(n: u64) -> TaskId { TaskId::new(n) }

fn tracker() -> (FakeClock, WorkCore<FakeClock>) {
    let clock = FakeClock::new(1_790_000_000_000, 0);
    let mut core = WorkCore::new(clock.clone());
    core.add_project(project(1), "TimerOS").unwrap();
    core.add_task(task(1), project(1), "I01").unwrap();
    core.add_task(task(2), project(1), "Especificar HUD").unwrap();
    (clock, core)
}

fn countdown(clock: &FakeClock, mode: CountdownMode) -> CountdownRun {
    let def = CountdownDefinition::new(CountdownId::new(1), "Agua", 25 * M, mode).unwrap();
    let mut run = CountdownRun::new(def);
    run.start(clock.sample()).unwrap();
    run
}

#[test]
fn duas_tarefas_simultaneas_60_min_projeto_60_tarefas_120() {
    let (clock, mut core) = tracker();
    core.start_task(task(1)).unwrap();
    core.start_task(task(2)).unwrap();
    clock.advance_both_ms(60 * M);
    let m = core.project_metrics(project(1)).unwrap();
    assert_eq!(m.own_elapsed_ms, 60 * M);
    assert_eq!(m.task_time_ms, 120 * M);
    assert_eq!(m.running_task_count, 2);
    core.pause_task(task(1)).unwrap();
    clock.advance_both_ms(30 * M);
    let m = core.project_metrics(project(1)).unwrap();
    assert_eq!(m.own_elapsed_ms, 90 * M);
    assert_eq!(m.task_time_ms, 150 * M);
    core.pause_task(task(2)).unwrap();
    clock.advance_both_ms(10 * M);
    assert_eq!(core.project_metrics(project(1)).unwrap().own_elapsed_ms, 90 * M);
}

#[test]
fn transicoes_de_atividade_projeto_0_1_1_0_sao_corretas() {
    let (clock, mut core) = tracker();
    core.start_task(task(1)).unwrap();
    clock.advance_awake_ms(10 * M);
    core.start_task(task(2)).unwrap();
    clock.advance_awake_ms(10 * M);
    core.pause_task(task(1)).unwrap();
    clock.advance_awake_ms(10 * M);
    core.pause_task(task(2)).unwrap();
    let m = core.project_metrics(project(1)).unwrap();
    assert_eq!(m.own_elapsed_ms, 30 * M);
    assert_eq!(m.task_time_ms, 40 * M);
}

#[test]
fn pause_resume_cria_sessoes_separadas_sem_duplicacao() {
    let (clock, mut core) = tracker();
    core.start_task(task(1)).unwrap();
    clock.advance_awake_ms(5 * M);
    core.pause_task(task(1)).unwrap();
    clock.advance_wall_ms(3_600_000);
    core.resume_task(task(1)).unwrap();
    clock.advance_awake_ms(7 * M);
    core.complete_task(task(1)).unwrap();
    let t = core.task(task(1)).unwrap();
    assert_eq!(t.status, TaskStatus::Completed);
    assert_eq!(t.entries().len(), 2);
    assert_eq!(core.task_elapsed_ms(task(1)).unwrap(), 12 * M);
    assert!(t.entries().iter().all(|e| e.ended_awake_ms.is_some()));
    assert_eq!(core.project_metrics(project(1)).unwrap().own_elapsed_ms, 12 * M);
}

#[test]
fn checkpoint_duplo_no_mesmo_instante_nao_acrescenta_tempo() {
    let (clock, mut core) = tracker();
    core.start_task(task(1)).unwrap();
    core.start_task(task(2)).unwrap();
    clock.advance_awake_ms(80_000);
    core.checkpoint_in_memory().unwrap();
    core.checkpoint_in_memory().unwrap();
    assert_eq!(core.project_metrics(project(1)).unwrap().own_elapsed_ms, 80_000);
    assert_eq!(core.project_metrics(project(1)).unwrap().task_time_ms, 160_000);
    clock.advance_awake_ms(20_000);
    core.pause_all_tasks().unwrap();
    assert_eq!(core.project_metrics(project(1)).unwrap().own_elapsed_ms, 100_000);
    assert_eq!(core.project_metrics(project(1)).unwrap().task_time_ms, 200_000);
}

#[test]
fn relogio_civil_nao_e_base_do_tempo_de_trabalho() {
    let (clock, mut core) = tracker();
    core.start_task(task(1)).unwrap();
    clock.advance_wall_ms(8 * 60 * 60 * 1000);
    assert_eq!(core.task_elapsed_ms(task(1)).unwrap(), 0);
    clock.advance_awake_ms(2 * M);
    clock.advance_wall_ms(-15 * 60 * 60 * 1000);
    assert_eq!(core.project_metrics(project(1)).unwrap().own_elapsed_ms, 2 * M);
    core.pause_task(task(1)).unwrap();
    assert_eq!(core.task_elapsed_ms(task(1)).unwrap(), 2 * M);
}

#[test]
fn nao_inicia_tarefa_duas_vezes_e_nao_duplica_sessao() {
    let (_clock, mut core) = tracker();
    core.start_task(task(1)).unwrap();
    assert_eq!(core.start_task(task(1)), Err(DomainError::InvalidTaskTransition));
    assert_eq!(core.task(task(1)).unwrap().entries().len(), 1);
    core.pause_task(task(1)).unwrap();
    assert_eq!(core.pause_task(task(1)), Err(DomainError::InvalidTaskTransition));
    core.complete_task(task(1)).unwrap();
    assert_eq!(core.resume_task(task(1)), Err(DomainError::InvalidTaskTransition));
}

#[test]
fn projetos_diferentes_nao_compartilham_tempo_proprio() {
    let (clock, mut core) = tracker();
    core.add_project(project(2), "Outro").unwrap();
    core.add_task(task(3), project(2), "Externa").unwrap();
    core.start_task(task(1)).unwrap();
    clock.advance_awake_ms(2 * M);
    core.start_task(task(3)).unwrap();
    clock.advance_awake_ms(3 * M);
    assert_eq!(core.project_metrics(project(1)).unwrap().own_elapsed_ms, 5 * M);
    assert_eq!(core.project_metrics(project(2)).unwrap().own_elapsed_ms, 3 * M);
}

#[test]
fn pause_all_usa_mesmo_instante_e_nao_retoma_sozinho() {
    let (clock, mut core) = tracker();
    core.start_task(task(1)).unwrap();
    core.start_task(task(2)).unwrap();
    clock.advance_awake_ms(45_000);
    assert_eq!(core.pause_all_tasks().unwrap(), 2);
    assert_eq!(core.pause_all_tasks().unwrap(), 0);
    clock.advance_awake_ms(100_000);
    assert_eq!(core.project_metrics(project(1)).unwrap().own_elapsed_ms, 45_000);
    assert_eq!(core.project_metrics(project(1)).unwrap().task_time_ms, 90_000);
}

#[test]
fn clock_monotonico_retrocedendo_e_rejeitado_sem_contar_tempo_negativo() {
    let (clock, mut core) = tracker();
    core.start_task(task(1)).unwrap();
    clock.advance_awake_ms(1_000);
    core.checkpoint_in_memory().unwrap();
    clock.set_awake_ms(500);
    assert_eq!(core.pause_task(task(1)), Err(DomainError::MonotonicClockReversed));
    assert_eq!(core.task(task(1)).unwrap().status, TaskStatus::Running);
}

#[test]
fn projeto_arquivado_nao_aceita_nova_tarefa() {
    let (_clock, mut core) = tracker();
    core.archive_project(project(1)).unwrap();
    assert_eq!(core.add_task(task(3), project(1), "nova"), Err(DomainError::ProjectArchived));
    assert_eq!(core.start_task(task(1)), Err(DomainError::ProjectArchived));
}

#[test]
fn countdown_prazo_absoluto_e_pendencia_idempotente() {
    let clock = FakeClock::new(100_000_000, 0);
    let mut run = countdown(&clock, CountdownMode::Cyclic);
    assert_eq!(run.state(), CountdownState::Running { due_at_utc_ms: 100_000_000 + 25 * M as i64 });
    clock.advance_wall_ms(25 * M as i64);
    assert!(run.evaluate_due(clock.sample()));
    assert!(!run.evaluate_due(clock.sample()));
    clock.advance_wall_ms(100 * M as i64);
    assert!(matches!(run.state(), CountdownState::Pending { .. }));
    assert_eq!(run.generation, 1);
}

#[test]
fn ciclico_so_reinicia_depois_do_reconhecimento() {
    let clock = FakeClock::new(0, 0);
    let mut run = countdown(&clock, CountdownMode::Cyclic);
    clock.advance_wall_ms(200 * M as i64);
    run.evaluate_due(clock.sample());
    run.acknowledge(clock.sample()).unwrap();
    assert_eq!(run.generation, 2);
    assert_eq!(run.state(), CountdownState::Running { due_at_utc_ms: 225 * M as i64 });
}

#[test]
fn oneshot_para_apos_reconhecimento() {
    let clock = FakeClock::new(0, 0);
    let mut run = countdown(&clock, CountdownMode::OneShot);
    clock.advance_wall_ms(25 * M as i64);
    run.acknowledge(clock.sample()).unwrap();
    assert_eq!(run.state(), CountdownState::Stopped);
    clock.advance_wall_ms(30 * M as i64);
    assert_eq!(run.state(), CountdownState::Stopped);
}

#[test]
fn pause_resume_nao_perde_restante_mesmo_com_suspensao() {
    let clock = FakeClock::new(0, 0);
    let mut run = countdown(&clock, CountdownMode::OneShot);
    clock.advance_wall_ms(10 * M as i64);
    run.pause(clock.sample()).unwrap();
    assert_eq!(run.state(), CountdownState::Paused { remaining_ms: 15 * M });
    clock.advance_wall_ms(7_200_000);
    assert_eq!(run.remaining_ms(clock.sample()).unwrap(), 15 * M);
    run.resume(clock.sample()).unwrap();
    assert_eq!(run.state(), CountdownState::Running { due_at_utc_ms: 7_200_000 + 25 * M as i64 });
}

#[test]
fn pause_no_vencimento_gera_pendencia_e_nao_pausa() {
    let clock = FakeClock::new(0, 0);
    let mut run = countdown(&clock, CountdownMode::Cyclic);
    clock.advance_wall_ms(25 * M as i64);
    assert_eq!(run.pause(clock.sample()), Err(DomainError::InvalidCountdownTransition));
    assert!(matches!(run.state(), CountdownState::Pending { .. }));
}

#[test]
fn snooze_nao_muda_duracao_original_nem_geracao() {
    let clock = FakeClock::new(0, 0);
    let mut run = countdown(&clock, CountdownMode::Cyclic);
    clock.advance_wall_ms(25 * M as i64);
    run.snooze(clock.sample(), 3 * M).unwrap();
    assert_eq!(run.generation, 1);
    assert_eq!(run.definition_snapshot.original_duration_ms, 25 * M);
    assert_eq!(run.state(), CountdownState::Running { due_at_utc_ms: 28 * M as i64 });
    clock.advance_wall_ms(3 * M as i64);
    assert!(run.evaluate_due(clock.sample()));
    run.reset(clock.sample()).unwrap();
    assert_eq!(run.state(), CountdownState::Running { due_at_utc_ms: 53 * M as i64 });
}

#[test]
fn reset_day_para_apenas_ciclicos_e_nao_reinicia() {
    let clock = FakeClock::new(0, 0);
    let mut cyc = countdown(&clock, CountdownMode::Cyclic);
    let one = countdown(&clock, CountdownMode::OneShot);
    let before = one.state();
    cyc.reset_day();
    assert_eq!(cyc.state(), CountdownState::Stopped);
    assert_eq!(one.state(), before);
}

#[test]
fn mudanca_de_fuso_simulada_sem_mudar_utc_nao_desloca_vencimento() {
    let clock = FakeClock::new(42_000, 0);
    let run = countdown(&clock, CountdownMode::Cyclic);
    assert_eq!(run.remaining_ms(clock.sample()).unwrap(), 25 * M);
    clock.advance_awake_ms(500_000); // simula alteracao nao-civil do ambiente
    assert_eq!(run.remaining_ms(clock.sample()).unwrap(), 25 * M);
    clock.set_utc_ms(42_001);
    assert_eq!(run.remaining_ms(clock.sample()).unwrap(), 25 * M - 1);
}

#[test]
fn valida_duracao_e_transicoes_invalidas() {
    assert_eq!(
        CountdownDefinition::new(CountdownId::new(1), "x", 0, CountdownMode::Cyclic),
        Err(DomainError::InvalidDuration)
    );
    let clock = FakeClock::new(0, 0);
    let mut run = countdown(&clock, CountdownMode::Cyclic);
    assert_eq!(run.start(clock.sample()), Err(DomainError::InvalidCountdownTransition));
    assert_eq!(run.acknowledge(clock.sample()), Err(DomainError::InvalidCountdownTransition));
    assert_eq!(run.snooze(clock.sample(), 0), Err(DomainError::InvalidDuration));
}
# TimerOS Core — I01

Implementacao inicial de dominio em Rust (`timeros-core`), independente de Slint,
Win32, SQLite, JSON, scheduler e audio. Este crate nao e o executavel Windows.

## Estrutura

- `clock`: `ClockSample` com UTC absoluto (prazos) e monotonic awake (trabalho),
  trait `Clock` e `FakeClock` para controlar ambos separadamente.
- `work`: projetos/tarefas/sessoes em memoria, transicoes de estado, check-point
  logico e metricas de projeto (uniao de intervalos, sem duplicar paralelismo).
- `countdown`: FSM inicial isolada com `Start/Pause/Resume/Due/Stop/Snooze/
  Acknowledge/Reset/ResetDay`, prazos absolutos e uma unica pendencia ciclica.
- `domain`: tipos de ID e erros explicitos.

## Testes

```sh
cargo test --all-targets
cargo fmt --all -- --check
```

Os testes usam apenas a biblioteca padrao. O `FakeClock` prova que alterar hora
civil nao acrescenta tempo progressivo e que vencimentos regressivos usam UTC.

## Escopo do incremento

I01 implementa **somente memoria de processo**, sem alegar que um checkpoint foi
persistido. Persistencia SQLite/JSON, crash recovery, coordenacao de commits e
migrations pertencem a I02. Recorrencia de alarmes fixos, perfis e som pertencem
a I03. FSM e editor de sequencias pertencem a I04. Adaptadores Slint/Win32 e
layout do HUD pertencem a I05/I06. Nao existem threads independentes por timer.

Fontes: T01 (dominio/trabalho), T03 (clock/countdown), T04 (limite de ciclos) e
PLAN da frente `implementacao-timeros-v1` (I01).
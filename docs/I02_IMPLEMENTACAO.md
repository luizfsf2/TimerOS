# TimerOS I02 — Persistencia e fluxo minimo Slint

## Entregue (codigo, sujeito a validacao Rust no QA)

- `migrations/0001_initial.sql`: cinco tabelas incluindo schema_migrations, indices parciais e chaves.
- `src/persistence/sqlite.rs`: repositório de trabalho com transacoes e WAL/FULL, confirmação por amostra monotônica, checkpoint único em lote, recuperação conservadora do crash, métricas de tempo próprio separado da soma das tarefas, teste de rollback injetado e fechamento explícito.
- `src/persistence/json.rs`: documentos `config.json` e `state.json` separados, envelopes v1, revisão/CAS, validação inicial, temp no mesmo diretorio + sync, substituição atômica, `.bak` anterior válido e preservação do arquivo corrompido sem restauração automática.
- `ui/app.slint` e `src/main.rs`: prova de caminho vertical projeto -> tarefa -> iniciar/pausar/retomar, confirmação após commit, atualização manual e checkpoint periódico (~60s).
- `tests/persistence_i02.rs`: testes de schema/FK, simultaneidade 60/120, checkpoints idempotentes, rollback, crash/restart, pausa/retomada, JSON backup/falha/corrupção/revisões.

## Uso no Windows

```powershell
cargo test --all-targets
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings
cargo run --features desktop --bin timeros
```

A UI Slint é **somente** a prova mínima da I02. Tray, HUD, always-on-top, comando X para ocultar, perfis/alarme/SequenceController, Windows notification e audio permanecem em I03-I05. O fechamento do protótipo pela janela executa encerramento seguro do processo (não implementa tray).

## Integridade e limites

- Arquivos são criados dentro de `data/` local. NUNCA usar DB compartilhado para validação. Nos testes todos os arquivos são descartáveis (`tempfile`).
- Os timestamps SQLite são UTC RFC3339 e **nunca** usados para reconstruir duração confirmada. O monotônico existe apenas em memória. Após reinício, a tarefa volta `paused`, mantendo só `confirmed_ms`.
- Não usar `cargo test --locked` sem reconciliar `Cargo.lock`: I02 introduziu dependências, e a atualização do lock precisa ser feita por desenvolvimento após QA, não pelo executor QA no checkout do produto.
- Os schemas internos completos de timers, alarmes, fases e ciclos pertencem a I03/I04. Aqui são validados envelopes/campos comuns e IDs, sem ativar run especializado.
- Não foi possível executar Rust nesta sessão: ausência local de `cargo/rustc` e de acesso à internet. Uma validação externa deve cobrir compilação da feature desktop, Rust fmt, clippy, testes, Windows real e a integridade do `Cargo.lock`.
- No Windows, rename/replace usa MoveFileExW(REPLACE_EXISTING|WRITE_THROUGH); é uma garantia de substituição atômica no mesmo volume, não garante sincronização de metadados em falha elétrica.
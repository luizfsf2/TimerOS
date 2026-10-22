# TimerOS I02 — Persistencia e fluxo minimo Slint

## Implementacao de desenvolvimento (I02)

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

- Arquivos são criados em `data/` ao lado do executável (não relativos ao CWD), preservando o diretório em distribuições portáteis. No Windows o processo segura um handle exclusivo de `data/.timeros.lock` durante toda a execução; uma segunda instância com a mesma pasta é recusada antes do boot/recuperação SQLite. O arquivo lock é preservado após saída e reutilizado após crash. NUNCA usar DB compartilhado para validação. Nos testes todos os arquivos são descartáveis (`tempfile`).
- Os timestamps SQLite são UTC RFC3339 e **nunca** usados para reconstruir duração confirmada. O monotônico existe apenas em memória. Após reinício, a tarefa volta `paused`, mantendo só `confirmed_ms`.
- O `Cargo.lock` da I01 está desatualizado para a I02: desenvolvimento deve executar `cargo generate-lockfile` ou `cargo update` no Windows com Cargo, versionar o resultado e validar `cargo fetch --locked` antes de fechar esta tarefa. Não fabricar lockfile nem promover a cópia temporária do QA sem validação.
- Os schemas internos completos de timers, alarmes, fases e ciclos pertencem a I03/I04. Aqui são validados envelopes/campos comuns e IDs, sem ativar run especializado.
- Não foi possível executar Rust nesta sessão: ausência local de `cargo/rustc` e de acesso à internet. Uma validação externa deve cobrir compilação da feature desktop, Rust fmt, clippy, testes, Windows real e a integridade do `Cargo.lock`.
- No Windows, rename/replace usa MoveFileExW(REPLACE_EXISTING|WRITE_THROUGH); é uma garantia de substituição atômica no mesmo volume, não garante sincronização de metadados em falha elétrica.
## QA-H3-implementacao-timeros-v1-001 (resultado de 2026-10-21)

- QA original em Windows: 28/28 testes Rust PASS e build/abertura Slint PASS; fmt FAIL, Clippy FAIL (2 lints) e lockfile FAIL. Interação manual ainda NOT RUN.
- Correções no código subsequentes: dois lints, diretório portátil e guarda exclusiva de instância Windows. Novos testes ainda exigem execução no Windows.
- Sem compilador Rust neste ambiente de autoria, **não** tratar essas edições como validação Rust nem encerrar a I02; atualizar lockfile e rodar QA independente em revisão nova.

## Revisao de desenvolvimento (2026-10-22)

O QA FORMAL `QA-H3-implementacao-timeros-v1-001` executou a revisao
`7277a488699f122d34fc3144780e18c927da8e4f` no Windows e encontrou
28 testes PASS, compilacao/smoke Slint PASS, Cargo.lock desatualizado, rustfmt
FAIL e dois avisos Clippy. Estes PASS **nao se aplicam automaticamente ao HEAD novo**.

Correcoes posteriores na `feature/v1`:
- Corrigidos os dois lints reportados, e recuperada formatação usando o diff real do rustfmt;
- Caminho de dados agora independe do CWD: `data/` fica junto ao executavel;
- Protecao Windows por arquivo aberto sem compartilhamento antes de recovery do SQLite;
- JSON nao recria defaults quando SQLite preexiste e verifica revisao em disco antes de substituir;
- Interface Slint da I02 permite selecionar projetos e tarefas existentes;
- Testes adicionais de integridade SQL, CAS de JSON, boot parcial e checkpoint falho;
- `scripts/prepare_i02_windows.ps1` para preparar e testar desenvolvimento local, SEM ser QA.

### Passo de desenvolvimento ainda obrigatorio

Em checkout limpo, branch `feature/v1` atualizada, rodar no Windows:

```powershell
.\scripts\prepare_i02_windows.ps1
```

O script gera `Cargo.lock` usando Cargo e registry reais, aplica rustfmt e
executa testes, Clippy e build, parando no primeiro erro. Revisar o diff e
commitar/push (na mesma branch autorizada, apos verificar triggers). Nao
versionar lockfile estimado/fabricado nem declarar sucesso sem logs reais.

### Aceite manual minimo antes do QA

Com `cargo run --locked --features desktop --bin timeros` em um diretorio de
dados descartavel, comprovar:
1. Criar dois projetos e pelo menos duas tarefas;
2. Alternar selecao de projeto/tarefa pela ComboBox e acionar iniciar, pausar,
   retomar; comprovar UI POS-COMMIT;
3. Deixar duas tarefas em paralelo e verificar tempo proprio contra soma;
4. Fechar a janela normalmente, reabrir o executavel em outro CWD e conferir
   persistencia em `data/` junto ao executavel;
5. Com primeira instancia ainda aberta, tentar abrir outra com a mesma `data/`;
   a segunda deve recusar sem executar `recover_interrupted`;
6. Usar data descartavel e observar checkpoint aos ~60s via SQLite;
7. Simular crash em dados descartaveis e conferir que somente duracoes
   confirmadas sobrevivem.

A rodada QA posterior e independente. I02 permanece aberta ate lockfile
versionado, validações Rust/Windows e resultados positivos. Nenhum helper H2
deve ser usado na rodada H3.

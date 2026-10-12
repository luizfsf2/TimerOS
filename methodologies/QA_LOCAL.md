# Metodologia — QA Local Assistido por Code Agent

QA é um papel de `EXECUÇÃO`. Checagens rápidas, comandos focais, inspeções e POCs pertencem ao desenvolvimento e não abrem rodada persistida de QA por padrão.

## 1. Quando usar o Code Agent QA

Use o Code Agent QA poucas vezes e em recortes coerentes, quando uma validação independente e ampla economizar mais tempo do que várias interações pequenas.

Toda rodada persistida usa o mesmo protocolo e um único `QA_ID`. O propósito é:

- `CHECKPOINT`: validação intermediária ampla o bastante para reduzir risco antes do próximo bloco;
- `FORMAL`: validação de fechamento do recorte definido.

Muda o propósito e a cobertura; não muda a mecânica básica.

QA não corrige produto por iniciativa própria. Defeito encontrado volta para Desenvolvimento.

## 2. Identidade e continuidade

Formato:

```text
QA-H3-<front_id>-<NNN>
```

`ACTIVE.md` reserva a rodada em `QA atual`. Número reservado não é reciclado após FAIL, BLOCKED, NOT RUN, cancelamento ou interrupção.

Bloqueio operacional recuperável não encerra a rodada. O executor pode pedir ao operador uma ação local pequena ou um esclarecimento; depois da resolução, retoma o mesmo `QA_ID` quando escopo e revisão continuarem válidos.

## 3. Pacote autocontido

O handoff deve ser rico o suficiente para o executor trabalhar sem reconstruir contexto por tentativa e erro.

Ao gerar ou reemitir o prompt/handoff de uma rodada persistida, a sessão controladora deve limpar o conteúdo de `RELATORIO_QA/` antes de escrever `PACOTE_QA.txt`, mantendo a própria pasta e confirmando por readback que ela ficou vazia. Esse diretório é o slot publicado da rodada corrente, não um arquivo histórico. Se evidência anterior ainda precisar ser durável, consolide-a no proprietário adequado antes da limpeza. Retomar a mesma rodada sem reemitir o pacote não dispara nova limpeza.

Cabeçalho mecânico mínimo:

```text
QA_CONTRACT_VERSION: H3.0.0
QA_ID: QA-H3-<front_id>-<NNN>
QA_PURPOSE: CHECKPOINT | FORMAL
front_id: <front_id>
HARNESS_REF: <SHA exato de 40 hex copiado do ACTIVE na emissão>
CREATED_AT: <timestamp ISO 8601 com timezone>
REVISION_POLICY: EXACT | BRANCH_CURRENT
EXPECT_BRANCH: <branch ou vazio>
EXPECT_HEAD: <sha ou vazio>
RESULT_DESTINATION: .tmp/qa/run/result/
```

O corpo deve trazer, de forma autocontida:

- objetivo;
- contexto e decisões relevantes;
- delta a validar;
- riscos conhecidos;
- comportamento esperado;
- testes/checagens já executados;
- escopo investigativo;
- limites e autorizações;
- contrato de retorno.

O campo `HARNESS_REF` é obrigatório porque o executor QA é isolado e não tem acesso ao ACTIVE no Drive. A sessão controladora deve copiá-lo literalmente do `Harness ref` vigente no momento da emissão. O ACTIVE permanece a fonte autoritativa; o pacote apenas transporta esse pin para o executor.

`CREATED_AT` também é obrigatório e registra somente quando o pacote foi criado ou reemitido. Use ISO 8601 com offset de timezone, por exemplo `2026-10-01T01:54:28-03:00`. Reemissão atualiza esse timestamp, mas não muda por si só `QA_ID`, revisão alvo ou semântica da rodada.

O executor nunca escolhe o harness por branch, HEAD, recência ou aparência de completude. O `HARNESS_REF` deve ser um SHA exato de 40 hex e deve coincidir com o `harness_ref` do `LAUNCH.json`. Ausência ou divergência bloqueia antes dos testes e não autoriza fallback para `.claude/qa/*`.

Se o `Harness ref` da frente mudar antes do início material da rodada, a sessão controladora reemite o pacote com o mesmo `QA_ID` quando escopo e revisão de produto permanecerem válidos; não invente nova rodada só para transportar o novo pin.

O pacote não depende do Drive, não contém URL/ID de Drive e não instrui publicação no Drive. Política e interpretação pertencem a esta metodologia e à governança; o helper valida somente o envelope mecânico.

## 4. Revisão alvo

`REVISION_POLICY: EXACT`:
- `EXPECT_HEAD` é vinculante;
- dirty relevante ou revisão incompatível exige `OPERATOR_ACTION_REQUIRED`;
- o preflight não retargeta o alvo.

`REVISION_POLICY: BRANCH_CURRENT`:
- `EXPECT_BRANCH` é vinculante;
- o HEAD observado no preflight é a revisão testada;
- `EXPECT_HEAD`, quando informado, é referência da emissão, não trava a rodada;
- dirty preexistente é baseline, não bloqueio por si só.

O preflight do helper é observacional: não faz merge, rebase, reset, force, stash, cherry-pick, commit, push, PR, CI nem corrige checkout. Preparação que exigir ação no checkout pode ser resolvida pelo operador e o preflight é repetido no mesmo `QA_ID`.

## 5. Execução

Priorize tempo total e cobertura por interação:

- execute checks baratos primeiro quando ajudarem a detectar bloqueios;
- paralelize testes independentes quando for seguro e vantajoso;
- continue gates independentes mesmo depois de uma falha;
- interrompa somente o que ficou inútil, dependente ou inseguro;
- investigue causa provável quando isso reduzir uma nova ida e volta;
- preserve artifacts úteis ao diagnóstico.

Workers, waves, classes fixas de custo e enums de concorrência não fazem parte do protocolo. Podem existir como detalhe interno da ferramenta ou do agente quando reduzirem tempo sem alterar escopo, segurança ou evidência.

## 6. Reuso de evidência

PASS anterior pode ser reaproveitado quando o delta posterior não o invalida materialmente.

Registre proveniência suficiente: rodada/revisão de origem, gate ou área, ambiente relevante, delta analisado e justificativa. Na dúvida material, reexecute.

## 7. Resultado

A rodada deve devolver em uma única interação, quando aplicável:

- resultado por área/gate: PASS, FAIL, BLOCKED ou NOT RUN;
- revisão efetivamente testada;
- comandos e procedimentos relevantes executados;
- falhas reproduzíveis e primeira evidência útil;
- causa provável claramente separada de fato confirmado;
- logs, screenshots/prints e artifacts;
- limitações;
- o que ainda precisa ser revalidado;
- ação necessária do operador, quando houver.

`OPERATOR_ACTION_REQUIRED` é estado de preparação/continuidade, não quinto veredito.

O REPORT local, quando produzido, resume esse retorno; logs completos ficam como artifacts.

## 8. Evidência local

```text
.tmp/qa/run/
├── PACOTE_QA.txt
├── LAUNCH.json
├── state.json
├── bootstrap/
│   └── <HARNESS_REF>/
│       ├── qa_launcher.py
│       ├── QA_AGENT_MAIN_PROMPT.md
│       └── qa_harness.py
├── artifacts/
└── result/
    ├── REPORT.md
    ├── EVIDENCE.json
    ├── screenshots/
    └── logs/
```

O workspace é efêmero e único por checkout. `prepare` define o início de uma nova sessão QA e limpa/recria todo `.tmp/qa/run/` antes de copiar o pacote e materializar o bootstrap pinado. `run/artifacts/` guarda fixtures, outputs de runners, traces e demais artefatos necessários para executar ou investigar os testes sem sujar caminhos de produto.

Cada execução de `preflight` limpa/recria somente `.tmp/qa/run/result/`, preservando pacote, manifesto, bootstrap, state e `run/artifacts/` da sessão corrente. O resultado final da sessão fica sempre em `.tmp/qa/run/result/`.

Como o pathname não carrega identidade, `front_id` e `QA_ID` continuam obrigatórios no pacote, manifesto, state, evidência e relatório. Um checkout comporta uma sessão QA ativa por vez.

O helper não interpreta resultado de produto. Ele valida pacote, observa revisão, prepara workspace, executa comandos e registra evidência mecânica.

## 9. Segurança

- não imprimir secrets, tokens, connection strings, cookies, sessões ou credenciais;
- não aplicar migration nem mutar banco/runtime/infra compartilhados sem autorização;
- não enfraquecer invariantes para fazer teste passar;
- não introduzir compatibilidade/legado por inferência;
- `.tmp/qa/run/` é efêmero e pode ser integralmente apagado por `prepare` ao iniciar uma nova sessão; já a limpeza do slot remoto `RELATORIO_QA/` é responsabilidade exclusiva da sessão controladora durante criação/reemissão do pacote;
- não alterar produto como parte do papel QA.

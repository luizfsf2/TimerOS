# QA harness (`.claude/qa/qa_harness.py`)

Ferramental mecânico do QA único do projeto. O harness padroniza validação do pacote, preparação Git, workspace, execução de comandos, paralelismo controlado, logs e verificação final. Ele não decide veredito funcional e não cria o `QA_ID`.

## Contrato H2.5.3

Antes de uma rodada nova:

```bash
uv run python .claude/qa/qa_harness.py --version
```

Saída esperada:

```text
H2.5.3
```

O pacote deve declarar `QA_CONTRACT_VERSION: H2.5.3`.

Regras centrais:

- isolamento local por frente: `.tmp/qa/<front_id>/`;
- QA_ID externo: `QA-<front_id>-<NNN>`;
- branch e HEAD são metadados do alvo, não identidade da rodada;
- dirty inicial não bloqueia QA nem exige autorização;
- o QA pode fazer `git fetch --prune origin`, trocar para a branch pedida e aplicar `git pull --ff-only`;
- branch local atrás do remoto por fast-forward é atualizada automaticamente;
- branch local à frente do remoto é testada no HEAD local;
- divergência, falha de switch/pull/fetch ou outro problema Git real retorna `OPERATOR_ACTION_REQUIRED`: o executor para antes dos testes e resolve com o operador humano na própria sessão local;
- o HEAD do pacote é referência do estado esperado, não bloqueio rígido; o commit efetivamente testado é sempre registrado;
- o `REPORT.md` só nasce depois de pacote válido e preflight concluído com `PROCEED`;
- o estado final compara o working tree com o baseline capturado depois da preparação Git; mudança nova causada durante o QA gera aviso por padrão, não FAIL automático;
- IDs de blocos de execução são validados antes de formar caminhos de log;
- no Windows, wrappers `.cmd/.bat` são chamados via `cmd.exe`;
- nenhuma dependência nova: somente stdlib.

## Ordem de início

1. validar o pacote;
2. executar o preflight Git;
3. se houver `OPERATOR_ACTION_REQUIRED`, resolver com o operador e repetir o preflight;
4. criar o workspace/`REPORT.md`;
5. executar os testes.

O preflight pode usar `.tmp/qa/<front_id>/` como área de preparação, mas não cria `REPORT.md`.

## `validate-package`

Valida versão do contrato, `QA_ID`, `front_id`, `MODO`, destino local canônico e ausência de dependência operacional de Google Drive.

```bash
uv run python .claude/qa/qa_harness.py validate-package \
  --front-id minha-frente \
  --qa-id QA-minha-frente-001 \
  --package-file .tmp/qa/minha-frente/package_input.txt
```

O guardrail rejeita URL/domínio de Drive, campos de URL/ID do Drive, `RESULT_DESTINATION` fora de `.tmp/qa/<front_id>/result/` e instruções positivas de leitura/publicação no Drive.

## `preflight`

```bash
uv run python .claude/qa/qa_harness.py preflight \
  --front-id minha-frente \
  --expect-branch wip/minha-branch \
  --expect-head <sha-de-referencia>
```

O comando faz `git fetch --prune origin` e prepara o checkout:

- branch diferente da pedida: tenta `git switch <branch>`;
- local atrás por fast-forward: tenta `git pull --ff-only origin <branch>`;
- local igual: prossegue;
- local à frente: prossegue no HEAD local;
- HEAD diferente do informado no pacote: registra a diferença e prossegue no HEAD efetivo;
- divergência ou falha real de Git: `OPERATOR_ACTION_REQUIRED`.

Dirty preexistente é apenas baseline. O harness não limpa, reseta, guarda em stash nem pede autorização por ele. Se o próprio `switch` ou `pull --ff-only` falhar por causa do estado local, isso vira problema operacional real e é tratado com o operador.

O preflight grava fingerprint de conteúdo do dirty relevante para detectar inclusive alteração posterior de arquivo que já estava sujo.

## `workspace`

Só pode iniciar após preflight com `PROCEED`:

```bash
uv run python .claude/qa/qa_harness.py workspace \
  --front-id minha-frente \
  --qa-id QA-minha-frente-001
```

Valida front_id/QA_ID, confirma `.tmp/` ignorado, recusa symlink, preserva os dados do preflight e cria `result/REPORT.md` com branch e commit efetivamente testados.

Reentrada da mesma rodada:

```bash
uv run python .claude/qa/qa_harness.py workspace \
  --front-id minha-frente \
  --qa-id QA-minha-frente-001 \
  --no-clean
```

## `delta`

```bash
uv run python .claude/qa/qa_harness.py delta \
  --front-id minha-frente \
  --from <sha-base> \
  --to <sha-alvo>
```

Grava a lista de arquivos Python existentes entre refs no workspace da frente.

## `run`

```bash
uv run python .claude/qa/qa_harness.py run \
  --front-id minha-frente \
  --id unit -- \
  uv run python -m pytest -q tests/unit/test_exemplo.py
```

O log integral vai para `.tmp/qa/<front_id>/logs/<id>.log`.

No Windows, candidatos executáveis de `PATHEXT` são preferidos a shims sem extensão; wrappers `.cmd/.bat` são encaminhados para `cmd.exe /d /c` com `shell=False`. Executável ausente retorna 127 e erro de spawn retorna 126 sem derrubar o harness.

## `run-parallel`

Blocos independentes executam em paralelo; blocos PostgreSQL são serializados automaticamente. Todos os IDs passam pela mesma validação segura de caminho.

## `final`

```bash
uv run python .claude/qa/qa_harness.py final --front-id minha-frente
```

Compara branch, HEAD e fingerprint dirty contra o estado capturado pelo preflight.

- branch/HEAD mudando depois do início efetivo do QA exige revisão e retorna erro;
- dirty preexistente é ignorado;
- mudança nova em arquivo relevante durante o QA é listada como `AVISO` e o comando permanece verde por padrão;
- o executor decide no REPORT se a mudança comprometeu o teste ou revelou comportamento incorreto relevante.

## `report-block`

```bash
uv run python .claude/qa/qa_harness.py report-block --front-id minha-frente
```

Emite Markdown auxiliar com QA_ID, branch, HEAD esperado, commit efetivamente testado, preparação Git e estado final.

## Self-test local recomendado

1. `--version`;
2. `validate-package` válido e inválido;
3. switch automático para a branch pedida;
4. fast-forward automático quando local está atrás;
5. execução normal quando local está à frente;
6. divergência retornando `OPERATOR_ACTION_REQUIRED` sem merge/rebase/reset;
7. dirty inicial sem bloqueio;
8. mudança nova durante QA aparecendo apenas como aviso no `final`;
9. `--no-clean` na mesma rodada;
10. `run --id` rejeitando path traversal;
11. no Windows, `run` com `npm --version` ou wrapper `.cmd` equivalente.

O system prompt e a metodologia definem papel, autonomia, vereditos e estratégia. Este README documenta somente a mecânica do script.

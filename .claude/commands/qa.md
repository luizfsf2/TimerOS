---
description: Execute o QA único do projeto em modo APOIO ou FORMAL, com preparação Git automática e workspace isolado por frente
argument-hint: [PACOTE QA]
---

Atue exclusivamente como executor de QA. Não implemente correções de produto e não delegue a execução.

==================================================
CONTRATO
==================================================

Há um único executor com dois modos:

- APOIO: investigação/teste focal durante desenvolvimento;
- FORMAL: validação consolidada de uma feature ou incremento materialmente coerente.

O PACOTE QA é autoridade sobre escopo, casos/gates, revisão desejada, alvo e autorizações adicionais.

O executor roda localmente no checkout e não possui acesso ao Google Drive. O pacote deve chegar integralmente no prompt ou por caminho local acessível. Link de Drive é somente comunicação entre sessão controladora e operador humano e nunca é dependência operacional do executor.

Pacotes novos declaram:

- QA_CONTRACT_VERSION: H2.5.3
- QA_ID: QA-<front_id>-<NNN>
- MODO: APOIO | FORMAL
- front_id
- Branch/HEAD esperado, quando relevante
- Objetivo e casos/gates
- Limites/autorização
- RESULT_DESTINATION: .tmp/qa/<front_id>/result/

QA_ID é reservado pela sessão controladora. Você não cria, incrementa, recalcula nem recicla QA_ID.

Antes de qualquer teste:

```bash
uv run python .claude/qa/qa_harness.py --version
```

A saída deve ser exatamente `H2.5.3` e coincidir com o pacote.

Valide também QA_ID, front_id e destino local. Se identidade ou versão estiverem inconsistentes, pare antes dos testes e peça reconciliação.

==================================================
ESTRATÉGIA
==================================================

APOIO:
- responda somente à pergunta técnica do pacote;
- não amplie para suíte formal por iniciativa própria.

FORMAL:
- execute os gates aplicáveis definidos no pacote;
- continue gates independentes e seguros mesmo quando outro falhar;
- suspenda apenas casos dependentes de bloqueio central;
- devolva FAILs materiais em lote.

Regra de custo:
- não repetir suíte verde sem causa material;
- mudança de HEAD, isoladamente, não invalida PASS anterior;
- preservar PASS quando o delta posterior não toca materialmente comportamento, contrato ou gate comprovado;
- reexecutar apenas gates materialmente invalidados.

==================================================
PAPEL E LIMITES
==================================================

Você PODE:
- ler código, testes, documentação e configuração;
- executar testes, lint, build e validações locais;
- iniciar e encerrar processos locais iniciados por você;
- usar browser/Playwright local;
- consultar logs, processos, portas e dependências;
- fazer consultas read-only permitidas;
- executar `git fetch --prune origin`;
- trocar para a branch pedida pelo pacote;
- executar `git pull --ff-only` quando a branch local estiver atrás;
- escrever somente em `.tmp/qa/<front_id>/`.

Você NÃO PODE:
- alterar código-fonte, testes, documentação rastreada, configuração, lockfiles ou .env;
- corrigir defeitos encontrados;
- criar commit, push, PR ou disparar CI;
- fazer merge, rebase, cherry-pick, reset ou force para resolver divergência;
- instalar/remover/atualizar dependências sem autorização específica;
- matar processo preexistente que você não iniciou;
- aplicar migration ou mutar banco/runtime/infra compartilhados sem autorização específica;
- publicar em Google Drive.

Working tree sujo não bloqueia QA e não exige autorização. Não limpe, resete nem faça stash. Se uma operação concreta de Git falhar por causa do estado local, trate como problema operacional real.

==================================================
ORDEM DE INÍCIO
==================================================

Siga esta ordem:

1. validar o pacote;
2. preparar Git/branch/HEAD com `preflight`;
3. se houver problema operacional real, parar e perguntar ao operador humano nesta mesma sessão;
4. somente após `PROCEED`, criar o workspace e o `REPORT.md`;
5. executar os testes.

Falha de preparação Git não fecha a rodada como BLOCKED formal, não produz REPORT final e não deve ser devolvida à sessão controladora como pingue-pongue operacional. Resolva com o operador e retome o mesmo QA_ID.

==================================================
GUARDRAIL DO PACOTE
==================================================

Se o pacote veio diretamente no prompt, grave uma cópia exata em `.tmp/qa/<front_id>/package_input.txt`. Isso é apenas staging; ainda não cria REPORT.

Execute:

```bash
uv run python .claude/qa/qa_harness.py validate-package \
  --front-id <front_id> \
  --qa-id <QA_ID> \
  --package-file <caminho-local-do-pacote>
```

O guardrail rejeita:
- URL/domínio de Google Drive;
- campos de URL/ID do Drive;
- destino diferente de `.tmp/qa/<front_id>/result/`;
- instrução positiva para abrir/ler/copiar/sincronizar/publicar no Drive;
- divergência de versão, QA_ID, front_id ou MODO.

Pacote inválido: pare antes do preflight/testes e peça reconciliação. Não o edite silenciosamente.

==================================================
PREFLIGHT GIT
==================================================

Use:

```bash
uv run python .claude/qa/qa_harness.py preflight \
  --front-id <front_id> \
  --expect-branch <branch> \
  --expect-head <sha-de-referencia>
```

O preflight faz `git fetch --prune origin` e prepara o checkout:

- branch diferente da pedida: tenta `git switch <branch>`;
- local atrás do remoto por fast-forward: tenta `git pull --ff-only origin <branch>`;
- local igual: prossegue;
- local à frente: prossegue no HEAD local;
- HEAD diferente do pacote: registra a diferença e prossegue; o HEAD do pacote é referência, não bloqueio rígido;
- divergência local/remoto: não resolve automaticamente;
- falha de fetch/switch/pull: não tenta contorno destrutivo.

Nos dois últimos casos o harness retorna `OPERATOR_ACTION_REQUIRED`. Pare antes dos testes, explique ao operador humano nesta sessão, resolva com ele e repita o preflight.

Dirty inicial é ignorado como gate. O preflight captura fingerprint de conteúdo do estado relevante depois da preparação Git para servir de baseline do estado final.

==================================================
WORKSPACE
==================================================

Após `PROCEED`:

```bash
uv run python .claude/qa/qa_harness.py workspace \
  --front-id <front_id> \
  --qa-id <QA_ID>
```

O diretório da frente pode existir durante guardrail/preflight, mas o `REPORT.md` só nasce aqui.

Estrutura:

```text
.tmp/qa/<front_id>/
├── logs/
└── result/
    ├── REPORT.md
    ├── screenshots/
    ├── logs/
    └── artifacts/
```

Reentrada na mesma rodada:

```bash
uv run python .claude/qa/qa_harness.py workspace \
  --front-id <front_id> \
  --qa-id <QA_ID> \
  --no-clean
```

==================================================
ALVO EFETIVAMENTE TESTADO
==================================================

O commit informado no pacote representa o estado esperado quando o pacote foi produzido.

Depois do preflight:
- local atrás: atualize por fast-forward e teste o HEAD resultante;
- local igual: teste esse HEAD;
- local à frente: teste o HEAD local;
- divergência: resolva com o operador antes dos testes.

O REPORT registra sempre o commit efetivamente testado.

Se o delta desde o pacote alterar materialmente critérios, ambiente, contratos ou casos, peça reconciliação do pacote. Delta não relacionado não invalida PASS anterior por si só.

==================================================
FERRAMENTAS DO HARNESS
==================================================

Arquivo: `.claude/qa/qa_harness.py`

Documentação: `.claude/qa/README.md`

`validate-package`
- valida contrato e destino;
- rejeita dependência operacional de Drive.

`preflight`
- prepara branch/HEAD;
- sincroniza fast-forward;
- permite local à frente;
- devolve `OPERATOR_ACTION_REQUIRED` quando a preparação exige decisão humana.

`workspace`
- só inicia após preflight verde;
- cria REPORT com branch e commit efetivamente testados.

`delta`
- lista arquivos Python existentes entre refs.

`run`
- valida ID do bloco;
- resolve executável;
- preserva log completo e imprime resumo compacto;
- no Windows, wrappers `.cmd/.bat` usam `cmd.exe`.

`run-parallel`
- executa blocos independentes em paralelo;
- serializa blocos PostgreSQL.

`final`
- compara branch/HEAD e fingerprint dirty contra o baseline;
- dirty preexistente não é finding;
- mudança nova durante QA é aviso por padrão;
- branch/HEAD mudando depois do início efetivo exige revisão.

`report-block`
- produz bloco auxiliar de Contexto/Resumo/Estado final.

==================================================
REGRA DE ESCRITA
==================================================

Toda escrita local do QA fica em `.tmp/qa/<front_id>/`.

Se um teste produzir mudança nova em arquivo rastreado fora de `.tmp/qa/`:
- preserve evidência;
- investigue a origem quando material;
- não reverta nem corrija;
- registre no REPORT;
- trate como aviso por padrão.

Só transforme em FAIL/BLOCKED quando a mudança comprometer o teste ou indicar comportamento incorreto relevante.

==================================================
ENDPOINTS E PROCESSOS LOCAIS
==================================================

Resolva portas a partir do `config.yaml` do checkout atual. Não presuma portas fixas.

Se uma porta estiver ocupada:
- identifique processo e checkout/CWD quando possível;
- reutilize somente se for a instância esperada;
- pode reiniciar processo iniciado por você;
- não mate processo preexistente sem autorização.

Registre os processos que iniciar e encerre-os ao final, inclusive em FAIL/BLOCKED, salvo instrução explícita em contrário.

==================================================
QUANDO UM TESTE NÃO RODA
==================================================

Não declare BLOCKED na primeira mensagem de erro.

Investigue proporcionalmente para distinguir:
- defeito funcional;
- defeito do teste;
- pacote/revisão desatualizada;
- dependência/configuração;
- serviço/porta;
- runtime incompatível;
- segredo/variável ausente;
- banco/migration;
- problema do harness;
- permissão.

Pode repetir teste após falha transitória, aguardar readiness e reiniciar somente processo iniciado por você.

==================================================
STATUS DOS CASOS
==================================================

Use exatamente:

- PASS
- FAIL
- BLOCKED
- NOT RUN

`OPERATOR_ACTION_REQUIRED` é estado de preparação Git antes dos testes, não um quinto status de caso e não gera REPORT final enquanto não for resolvido.

==================================================
EVIDÊNCIAS E RELATÓRIO
==================================================

REPORT.md deve ser pequeno e predominantemente textual.

Formato mínimo:

```markdown
# Relatório de QA

## 1. Contexto
- QA_ID:
- Front ID:
- QA_CONTRACT_VERSION: H2.5.3
- Branch:
- HEAD esperado no pacote:
- HEAD remoto observado:
- Commit efetivamente testado:
- Preparação Git realizada:
- Working tree relevante inicial:
- Runtime relevante:
- Backend local:
- Frontend local:
- Fonte dos endpoints:
- Data/hora:
- Pacote desatualizado: SIM | NAO | NAO DETERMINAVEL

## 2. Resumo
| Caso | Status | Evidência principal |
|---|---|---|

## 3. Casos executados
...

## 4. Falhas e bloqueios
...

## 5. Evidências
...

## 6. Investigações adicionais
...

## 7. Estado final
- Mudanças novas durante o QA:
- Efeito das mudanças novas: AVISO | FAIL | BLOCKED | N/A
...
```

Ao final:

```bash
uv run python .claude/qa/qa_harness.py final --front-id <front_id>
```

Se `final` listar mudanças novas, registre-as. Não converta automaticamente PASS funcional em FAIL; faça isso apenas se a mudança comprometer o teste ou revelar comportamento incorreto material.

==================================================
RESPOSTA FINAL
==================================================

Responda de forma curta com:
- `<front_id> — <QA_ID>`;
- status geral;
- tabela compacta PASS | FAIL | BLOCKED | NOT RUN;
- principal falha/bloqueio e solução, quando houver;
- caminho local de `result/` e `REPORT.md`;
- quantidade de screenshots/logs/artifacts;
- confirmação do estado final e eventual aviso de mudanças novas.

Não despeje logs nem o REPORT integral salvo pedido explícito.

A publicação posterior para o Drive pertence à sessão controladora.

==================================================
ENCERRAMENTO
==================================================

Não implemente correções.
Não altere ambiente compartilhado sem autorização.
Não produza plano de implementação de produto por iniciativa própria.
Ao terminar, aguarde a sessão controladora.

==================================================
PACOTE QA
==================================================

$ARGUMENTS

Execute exatamente o pacote acima, respeitando escopo, dependências e autorizações.
# FRONT_TEMPLATE — Harness V3

Escolha primeiro um `front_id` plano, seguro e único. Ele deve casar `^[A-Za-z0-9][A-Za-z0-9._-]*$`, não pode ser `.` nem `..` e não pode conter `/` ou `\\`.

Crie a frente nova em `tmp/active/<front_id>/`, sempre como diretório filho imediato de `tmp/active/`, com apenas:
- `ACTIVE.md`;
- `PLAN.md`.

Nunca crie uma frente dentro da pasta de outra frente. Relação pai/filha é topologia lógica no ACTIVE/FRONT_TREE, não hierarquia física de pastas.

Crie `NOTAS.md`, HISTORY/SUBPLAN e QA somente quando necessários.

Não criar CHECKLIST separado.

## ACTIVE.md

```markdown
# ACTIVE — <front_id>

front_id: <front_id>
Status: ACTIVE
Modo: GESTÃO
Harness ref: <SHA exato da definição do harness>
Branch: <branch | não aplicável | não confirmado>
HEAD observado: <sha | não aplicável | não confirmado>
Tarefa corrente: <task_id — título | não aplicável>
QA atual: NENHUM
Atualização: <AAAA-MM-DD>

## Último fato comprovado

<somente o fato necessário para retomada>

## Autorizações e bloqueios

- <somente autorizações/bloqueios que afetam o próximo passo>

## Próxima ação

<uma ação segura e concreta>
```

`Harness ref` fixa a definição da frente e não acompanha automaticamente a branch/HEAD de trabalho.

ACTIVE é snapshot; substitua conteúdo obsoleto em vez de acumular histórico. Use `não aplicável` somente para ausência semântica comprovada em campo que precise existir e `não confirmado` quando o estado deveria existir ou ser verificável mas ainda não foi reconciliado.

### Topologia opcional

Frente independente não inclui campos de topologia.

Quando houver relação lógica de filha, a filha continua fisicamente irmã do pai em `tmp/active/`. Acrescente ao ACTIVE:

```markdown
Frente-pai: <front_id>
Origem no pai: <motivo/recorte>
```

O retorno normal é implicitamente o pai. Acrescente `Retorno ao concluir: <front_id>` somente quando o destino for diferente do pai ou quando houver necessidade real de explicitação.

Não infira topologia de branch, commit, horário, proximidade temática ou ordem de criação.

## PLAN.md

```markdown
# PLAN — <front_id>

Objetivo: <resultado da frente>

## Decisões duráveis

- <somente decisões ainda relevantes>

## Tasks

[ ] 1.1 — <título>

Objetivo:
<...>

Aceite:
- <...>

Dependências/gates:
- <...>

Evidência mínima:
- <...>
```

PLAN é o único proprietário de task/status/aceite/dependências/evidência mínima.

Estados: `[ ]` pendente, `[x]` concluída, `[!]` bloqueada.

## NOTAS.md opcional

Scratchpad não autoritativo. Não substitui ACTIVE, PLAN, HISTORY, fonte proprietária, evidência obrigatória ou gate.

## HISTORY/SUBPLAN opcionais

Criar apenas quando histórico concluído ou detalhe grande prejudicar a navegação do PLAN. Não colocar estado corrente concorrente.

## QA opcional

Checagens rápidas de desenvolvimento não criam arquivos por padrão. Para rodada QA persistida:

```text
PACOTE_QA.txt
RELATORIO_QA/
```

QA_ID H3: `QA-H3-<front_id>-<NNN>`.

O ACTIVE preserva `QA atual: NENHUM | QA-H3-<front_id>-<NNN>` como reserva/continuidade da rodada, não histórico.

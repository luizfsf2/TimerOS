# Harness V3 — candidato

Definicao generica candidata do Harness H3.0.1 para projetos independentes, distribuida pelo instalador com baseline verificavel.

Este README é orientativo. Contratos autoritativos vivem nos arquivos proprietários indicados por `AGENTS.md`.

## Arquitetura

Cada projeto tem seu proprio repositorio e sua branch orfa `harness`, separada das branches de produto. Repositorios distintos podem ter SHAs diferentes para conteudo equivalente.

- `harness`: linha isolada de manutenção/discovery do harness;
- branches de produto: evolução do software;
- não há merge produto ↔ harness.

A definição aplicada não é “o HEAD atual de `harness`”. Cada frente fixa um commit exato no próprio:

```text
Harness ref: <SHA_EXATO>
```

Diferentes frentes podem usar revisões diferentes simultaneamente. Avançar `harness` não altera frentes existentes.

## Bootstrap

As Configuracoes do Projeto fornecem:
- `HARNESS_REPOSITORY` (definicao e QA);
- `PRODUCT_REPOSITORY` (codigo e documentos);
- `HARNESS_BRANCH` (`harness`);
- `WORKSPACE_ROOT`;
- `PRODUCT_PROFILE` opcional.

Para uma frente existente:
1. localize e leia seu `ACTIVE.md` no Drive;
2. obtenha `Harness ref`;
3. leia `AGENTS.md` e demais contratos diretamente do Git nesse SHA.

Sem frente aplicável, o HEAD da branch `harness` pode ser resolvido apenas para bootstrap/discovery. Ao criar uma frente, o SHA exato resolvido é gravado no ACTIVE.

Não existe mirror obrigatório do harness no Drive.

## Fronteira de propriedade

Git/harness:
- roteamento;
- contratos de modo;
- governança;
- operação documental;
- metodologias;
- templates;
- QA tooling;
- validadores/testes;
- recuperação/versionamento;
- modelo das Configurações do Projeto.

Drive em `WORKSPACE_ROOT/tmp/`:
- `active/FRONT_TREE.md`;
- ACTIVE/PLAN;
- NOTAS/HISTORY/SUBPLAN quando necessários;
- pacotes/resultados QA quando necessários;
- demais estado operacional autorizado.

Configurações do Projeto:
- localização do repositório;
- localização do workspace;
- bootstrap mínimo anterior ao `AGENTS.md`.

Produto:
- fontes opcionais explicitadas em PRODUCT_PROFILE (nenhum PRD ou glossario obrigatorio);
- codigo, migrations, testes, configuracao e integracoes;
- AGENTS locais.

## Estrutura

```text
AGENTS.md
GOVERNANCA.md
OPERACAO_DOCUMENTAL.md
CONFIGURACOES_PROJETO_CHATGPT.md
README.md
Modos/
docs/
methodologies/
templates/
prompts/
tools/
validators/
tests/
```

## Autoria e publicação

Branches de trabalho do harness derivam da linha `harness` conforme necessidade. Worktree separado é uma prática útil de autoria, não requisito de bootstrap.

Em branch autorizada, commit, push e atualização de ref remota podem avançar sem autorização adicional, desde que não provoquem outro efeito gated não autorizado. PR, CI, merge, tag e release continuam sujeitos a `GOVERNANCA.md`.

## Validação

Validação local barata pertence a `validators/` e `tests/`. Estratégia de QA pertence a `methodologies/QA_LOCAL.md`.

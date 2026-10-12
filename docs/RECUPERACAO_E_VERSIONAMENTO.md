# Recuperação e versionamento do Harness V3

A revisão do harness é propriedade de cada frente. `HARNESS_REPOSITORY` vem das Configurações do Projeto; `Harness ref: <SHA exato>` vive no `ACTIVE.md` e identifica a definição aplicada.

## Recuperação de frente existente

1. obtenha `HARNESS_REPOSITORY`, `PRODUCT_REPOSITORY`, `HARNESS_BRANCH` e `WORKSPACE_ROOT`;
2. selecione a frente e leia `WORKSPACE_ROOT/tmp/active/<front_id>/ACTIVE.md`;
3. obtenha `Harness ref` e exija SHA exato;
4. leia `AGENTS.md` diretamente do Git nesse SHA;
5. siga o roteamento e leia PLAN; expanda HISTORY/QA/metodologias somente se necessário.

Se `Harness ref` estiver ausente ou inválido, bloqueie a recuperação dependente. Não substitua silenciosamente por HEAD de `harness`, latest, outro front ou memória da conversa. Não existe mirror obrigatório da definição no Drive.

## Sem frente / nova frente

Sem frente aplicável, resolva o HEAD atual da branch `harness` para um SHA exato somente para bootstrap em GESTÃO. Ao criar uma frente, grave esse SHA em `Harness ref:` antes do trabalho material. Avanços posteriores da branch `harness` não alteram a frente.

## Perda forte de contexto

Recupere ACTIVE, `AGENTS.md` no SHA da frente e PLAN. Depois carregue somente contrato do modo ativo e as fontes adicionais realmente necessárias. Conversa/memória não renova autorização nem revisão aplicada.

## Divergência

Confirme primeiro o efeito real; reconcilie ACTIVE/PLAN; regenere FRONT_TREE somente se a projeção mudou; então avance.

## Troca de revisão

Alterar a revisão de uma frente significa atualizar explicitamente seu `Harness ref` para outro SHA conhecido conforme os gates aplicáveis. Não misture arquivos de dois SHAs na mesma sessão. Frentes diferentes podem permanecer em revisões diferentes.

A branch `harness` é linha de manutenção/discovery. Branches auxiliares e worktrees são mecanismos de autoria, não parte da identidade aplicada. Tags, releases e outros efeitos remotos seguem `GOVERNANCA.md`.


## Distribuicao generica

O kit `instalador-h3.0.1` guarda bytes do baseline e locks SHA-256. Um produto novo tem branch orfa `harness` com commit raiz sem pais. Se a branch ja existe, nunca reescrever a raiz ou fazer force-push; analisar equivalencia de conteudo ou planejar migracao separadamente. Atualizacoes genéricas so entram por patch aprovado.

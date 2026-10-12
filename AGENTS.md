# AGENTS.md — roteador do Harness V3

## Papel

Este arquivo é o ponto de entrada da definição já pinada do harness. Ele roteia modo, contexto e proprietário; não duplica governança, operação documental, metodologia, QA ou estado da frente.

Pré-condição de bootstrap:
- frente existente: as Configurações já localizaram o ACTIVE e resolveram seu `Harness ref` para este SHA exato;
- sem frente: as Configurações resolveram temporariamente o HEAD da branch `harness` para um SHA exato apenas para bootstrap/discovery.

A definicao sempre usa (HARNESS_REPOSITORY, SHA), e o checkout de produto usa PRODUCT_REPOSITORY; nao combinar repositorios. Toda leitura da definição desta sessão deve permanecer no mesmo SHA até uma transição explícita de `Harness ref`. Não misture arquivos de revisões diferentes.

## 1. Resolver modo

Precedência:
1. diretiva explícita `MODO: GESTÃO` ou `MODO: EXECUÇÃO` na mensagem corrente;
2. campo `Modo:` do ACTIVE da frente;
3. `GESTÃO` como default.

Se uma diretiva explícita mudar o modo de uma frente, persista o novo valor no ACTIVE conforme `OPERACAO_DOCUMENTAL.md`.

Carregue somente:
- `Modos/GESTAO.md`; ou
- `Modos/EXECUCAO.md`.

Não carregue os dois por rotina. O agente nunca troca de modo autonomamente.

GESTÃO e EXECUÇÃO compartilham as mesmas capacidades técnicas e estão sujeitos aos mesmos gates. A diferença entre eles é o regime de trabalho: GESTÃO prioriza deliberação e qualidade da decisão antes da materialização; EXECUÇÃO prioriza realização eficiente dentro de um escopo suficientemente definido. Capacidade técnica não equivale a autorização.

## 2. Retomada e roteamento da frente

Com frente ativa, ACTIVE é sempre o snapshot inicial e fornece modo, `Harness ref`, branch/HEAD observado quando aplicável, task corrente e próxima ação. Depois disso, roteie contexto pelo modo e pelo recorte real:

### GESTÃO

- use a solicitação corrente, ACTIVE e as fontes proprietárias necessárias para compreender e confrontar a direção;
- leia somente a seção pertinente do PLAN quando houver decisão, task, aceite, dependência ou risco durável que realmente governe a discussão;
- amplie para PRD/Glossário, implementação, arquitetura, segurança, histórico funcional ou metodologia somente quando isso puder mudar materialmente a recomendação;
- depois de `AUTORIZO`, carregue as fontes de implementação/validação necessárias ao recorte autorizado e execute-o sem reconstruir a deliberação nem pedir confirmação por arquivo ou por microdecisão equivalente;
- se surgir fato novo material, amplie contexto somente no proprietário afetado e interrompa apenas o recorte dependente conforme `Modos/GESTAO.md`.

### EXECUÇÃO com plano formal aplicável

- leia somente a task corrente do PLAN e seus elementos necessários: objetivo, aceite, dependências/gates, decisões duráveis e evidência esperada;
- carregue as fontes proprietárias, implementação e testes necessários para realizar e validar essa task;
- não reconstrua a deliberação que já está consolidada no PLAN ou em outra fonte proprietária;
- não leia histórico concluído, alternativas descartadas ou contexto amplo por rotina.

### EXECUÇÃO sem plano formal aplicável

- use a solicitação explícita, ACTIVE e as fontes proprietárias relevantes como base do recorte;
- não crie, expanda ou leia PLAN apenas para satisfazer cerimônia quando nenhuma task formal governa o pedido;
- PLAN existente é consultado somente se contiver decisão, limite ou dependência que realmente afete o trabalho solicitado;
- carregue implementação, testes e configuração no menor recorte suficiente para executar e validar;
- se surgir nova decisão material, conflito de fonte, gate ou fato novo, interrompa somente o recorte dependente, explique o impacto e peça a menor decisão ou ação necessária conforme `Modos/EXECUCAO.md`.

### Bootstrap de QA V3

Para qualquer frente V3, o executor QA deve nascer da definição pinada da própria frente, nunca do checkout de produto.

Sequência obrigatória:
1. antes de criar ou reemitir `PACOTE_QA.txt` para um novo prompt de execução, esvazie o conteúdo de `RELATORIO_QA/`, mantendo a própria pasta; se ela não existir, crie-a; confirme por readback que o slot está vazio;
2. registre `CREATED_AT` com o instante real da criação/reemissão em ISO 8601 com timezone e use sempre `RESULT_DESTINATION: .tmp/qa/run/result/`;
3. copie o `Harness ref` exato do ACTIVE para o campo obrigatório `HARNESS_REF`; o ACTIVE continua sendo a autoridade e o pacote é o transporte executável desse pin;
4. o executor isolado lê `HARNESS_REF` do pacote e nunca infere revisão a partir de branch, HEAD, recência ou helper do produto;
5. materialize temporariamente `tools/qa_launcher.py` daquele SHA exato fora de `.tmp/qa/run/` e execute `prepare --package-file <PACOTE_QA.txt>`;
6. `prepare` inicia uma nova sessão: limpa/recria `.tmp/qa/run/`, preserva uma cópia exata do pacote, cria `run/artifacts/` e materializa launcher/prompt/helper pinados;
7. carregue o prompt materializado e use somente o launcher/helper do `LAUNCH.json`;
8. trate o checkout de produto apenas como `--product-worktree <checkout>`; cada execução de `preflight` limpa/recria somente `.tmp/qa/run/result/`.

Os arquivos `.claude/commands/qa.md`, `.claude/qa/qa_harness.py` e demais helpers `.claude/qa/*` do checkout de produto são legado para uma frente V3. Não os leia, execute, importe nem use como fallback.

Se o `Harness ref`, o prompt ou o helper do SHA exato não puderem ser resolvidos, interrompa o bootstrap de QA. Ausência do artefato pinado é bloqueio; nunca autoriza fallback para o harness local do produto.

Sem frente ativa, permaneça em GESTÃO. Para criar frente, carregue `GOVERNANCA.md`, `OPERACAO_DOCUMENTAL.md` e `templates/FRONT_TEMPLATE.md`.

Não escolha frente por recência e não infira relação entre frentes a partir de branch, commit ou proximidade temporal.

## 3. Proprietários

| Necessidade | Proprietário |
|---|---|
| regime deliberativo de GESTÃO | `Modos/GESTAO.md` |
| regime de realização em EXECUÇÃO | `Modos/EXECUCAO.md` |
| autoridade, gates, Git/CI, ambiente, legado e release | `GOVERNANCA.md` |
| frentes, ACTIVE/PLAN, topologia, escrita operacional e handoff | `OPERACAO_DOCUMENTAL.md` |
| planejamento de fase/feature | `methodologies/PLANEJAMENTO_E_IMPLEMENTACAO.md` |
| interface e validação visual | `methodologies/INTERFACE_E_VALIDACAO_VISUAL.md` |
| QA e testes | `methodologies/QA_LOCAL.md` |
| nova frente | `templates/FRONT_TEMPLATE.md` |
| pacote de QA | `templates/PACOTE_QA_TEMPLATE.txt` |
| bootstrap/launcher de QA V3 | `tools/qa_launcher.py` |
| executor QA | `prompts/QA_AGENT_MAIN_PROMPT.md` + `tools/qa_harness.py` do mesmo `Harness ref` |
| recuperação/versionamento do harness | `docs/RECUPERACAO_E_VERSIONAMENTO.md` |

Produto/software permanece no `PRODUCT_REPOSITORY`, nunca no core distribuido:
- use caminhos opcionais explicitados em `PRODUCT_PROFILE` para PRD, glossario, status e normas locais, somente quando configurados e existentes;
- codigo, migrations, testes, configuracoes e integracoes do checkout do produto mostram o implementado;
- AGENTS locais do produto seguem como regras da area, sem substituir a definicao H3 pinada.
- sem perfil de produto, use as fontes reais encontradas no repositorio declarado, sem inventar PRD, glossario, STATUS_ATUAL ou caminhos de qualquer outro produto.
- sem HARNESS_REPOSITORY ou PRODUCT_REPOSITORY, BLOCKED, nunca fallback ao repositorio do projeto de origem.

## 4. Contexto proporcional

Carregue somente o necessário para decidir ou executar a próxima ação.

A largura do contexto segue o regime:
- em GESTÃO, amplie o suficiente para comparar consequências e melhorar a decisão;
- em EXECUÇÃO, aprofunde apenas o recorte necessário para implementar e validar com segurança.

Por rotina, não carregue:
- PLAN inteiro quando uma seção ou nenhum trecho basta;
- HISTORY quando ACTIVE/PLAN bastarem;
- todas as metodologias;
- QA antigo;
- logs/screenshots/artifacts;
- PRD/Glossário completos quando um recorte basta;
- outras frentes;
- o contrato do modo inativo;
- documentação de recuperação;
- deliberação encerrada quando o trabalho corrente já está suficientemente definido.

Expanda contexto quando houver gate, dúvida funcional, decisão material, divergência entre estado documental e efeito real, perda forte de contexto ou necessidade concreta do recorte.

Fato novo material amplia contexto somente onde puder alterar a decisão ou execução afetada. Não use um bloqueio localizado para reconstruir contexto independente nem para parar trabalho seguro que não dependa dele.

Conversa e memória são pistas de localização, nunca autoridade de requisito, estado, autorização, revisão, HEAD ou evidência.

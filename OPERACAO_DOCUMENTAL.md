# OPERACAO_DOCUMENTAL.md — Harness V3

Estado operacional: CANDIDATA V3.0.1.
Proprietário do workspace operacional no Drive, da memória das frentes e da mecânica documental. Autoridade e gates pertencem a `GOVERNANCA.md`; comportamento pertence ao contrato do modo ativo em `Modos/`.


## 1. Fronteira Git × Drive × Configurações

A definição do harness vive no Git. Em frente V3 ativa, o commit exato aplicável é o `Harness ref: <SHA>` do respectivo ACTIVE. Depois de resolvido, os contratos da sessão são lidos nesse SHA e não se misturam revisões.

O Drive em `WORKSPACE_ROOT` mantém estado operacional mutável sob `tmp/`:
- `tmp/active/FRONT_TREE.md`;
- `tmp/active/<front_id>/ACTIVE.md` e `PLAN.md`, onde cada `<front_id>` é um único diretório filho imediato de `tmp/active/`;
- `NOTAS.md`, `HISTORY.md` e `SUBPLAN_*.md` quando necessários;
- `PACOTE_QA.txt` e `RELATORIO_QA/` quando houver QA persistido;
- `tmp/completed/<front_id>/` para frentes encerradas ainda úteis à retomada;
- backlog operacional quando mantido e autorizado.

As Configurações do Projeto guardam somente os localizadores necessários, incluindo `HARNESS_REPOSITORY`, `PRODUCT_REPOSITORY`, `HARNESS_BRANCH` e `WORKSPACE_ROOT`, mais `PRODUCT_PROFILE` opcional. Não existe referência global que substitua o `Harness ref` de cada frente.

Mirror/cache da definição no Drive não faz parte do contrato mínimo. Se alguma ferramenta mantiver cache local, ele é otimização descartável e nunca autoridade de definição ou estado.

## 2. Frente e arquivos

A identidade estável é `front_id`; branch é atributo.

`front_id` deve ser um único segmento seguro e plano. Regra mecânica: deve casar `^[A-Za-z0-9][A-Za-z0-9._-]*$` e não pode ser `.` nem `..`. São proibidos `/` e `\\`. O valor de `front_id` é também o nome físico da pasta da frente.

Consequências obrigatórias:
- toda frente ativa é diretório filho imediato de `tmp/active/`;
- toda frente concluída é diretório filho imediato de `tmp/completed/`;
- frente filha nunca fica dentro da pasta da frente-pai;
- derivação lógica não cria hierarquia física;
- ao criar frente derivada, escolha um novo `front_id` plano e único; represente o parentesco somente por `Frente-pai` e `Origem no pai`.

Frente nova:

```text
tmp/active/<front_id>/    # <front_id> é um único segmento; nunca contém /
├── ACTIVE.md
└── PLAN.md
```

Sob demanda:

```text
├── NOTAS.md
├── HISTORY.md
├── SUBPLAN_<task_id>_<slug>.md
├── PACOTE_QA.txt
└── RELATORIO_QA/
    ├── REPORT.md
    ├── screenshots/
    ├── logs/
    └── artifacts/
```

Não criar `CHECKLIST.md` separado.


### ACTIVE.md

É snapshot curto do presente operacional, não diário. Deve manter somente o necessário para retomada:
- `front_id`;
- `Status`;
- `Modo: GESTÃO | EXECUÇÃO`;
- `Harness ref: <SHA exato>` para frente V3;
- `Branch` e `HEAD observado` separados quando aplicáveis;
- `Tarefa corrente`;
- `QA atual: NENHUM | QA-H3-<front_id>-<NNN>`;
- topologia somente quando houver relação lógica real;
- último fato comprovado necessário;
- autorizações e bloqueios correntes;
- próxima ação segura.

`Harness ref` é independente da branch/HEAD de trabalho da frente. Avançar uma branch não altera silenciosamente a definição aplicada à frente.

Campos mutáveis são substituídos, não acumulados. `QA atual` é reserva/continuidade da rodada QA corrente, não histórico.

### PLAN.md

É o único proprietário do plano formal:
- tasks e IDs;
- status/checkbox;
- objetivo e aceite;
- dependências/gates;
- decisões e riscos duráveis ainda relevantes;
- evidência mínima suficiente.

Estados sugeridos: `[ ]` pendente, `[x]` concluída, `[!]` bloqueada.

PLAN organiza o trabalho formal da frente quando aplicável, mas não transforma plano formal em pré-condição universal para toda solicitação em EXECUÇÃO. A semântica de execução direta pertence a `Modos/EXECUCAO.md`.

PLAN não vira journal, dump de logs, estado de branch/HEAD ou cópia de relatório. Task concluída deve ser compactada para resultado, aceite, decisão durável, evidência atribuível e limite ainda vigente.

### NOTAS.md

Opcional e não autoritativo. Pode organizar hipóteses, achados intermediários, comparações, lembretes e mini-checklists. Não é proprietário de decisão, autorização, requisito, bloqueio, estado, evidência obrigatória nem próximo passo. Em GESTÃO, sua criação/edição/limpeza segue o contrato do modo e não substitui materialização nos proprietários reais.

### HISTORY.md e SUBPLAN

HISTORY nasce somente quando histórico concluído começa a prejudicar a navegação do PLAN. SUBPLAN existe apenas quando um recorte realmente precisa de detalhe separado. Nenhum deles guarda estado corrente concorrente.


## 3. Modo e topologia opcional

Precedência de modo:
1. diretiva explícita `MODO: GESTÃO` ou `MODO: EXECUÇÃO` na mensagem corrente;
2. campo `Modo:` do ACTIVE;
3. `GESTÃO` como default.

Uma diretiva explícita `MODO:` é persistida no ACTIVE antes de continuar o trabalho. O agente nunca muda o modo autonomamente.

A transição de modo muda o regime cognitivo/interacional, não as capacidades técnicas nem os gates. A semântica comportamental permanece proprietária de `Modos/`.

Topologia representa somente relação lógica de trabalho e nunca estrutura física de pastas:
- frente independente omite campos de topologia;
- frente filha registra `Frente-pai: <front_id>` e `Origem no pai: <motivo/recorte>`;
- a pasta da filha continua como irmã da pasta do pai, diretamente sob `tmp/active/`;
- o retorno normal ao concluir é implicitamente o pai;
- `Retorno ao concluir: <front_id>` aparece apenas quando o destino for diferente do pai ou quando houver necessidade real de explicitação.

Não inferir parentesco ou retorno a partir de branch, commit, horário, proximidade temática ou ordem de criação.

`não aplicável` significa ausência semântica comprovada em campo operacional que precise existir. `não confirmado` significa estado esperado ou verificável que ainda não foi reconciliado. Não preencher topologia ausente com esses marcadores apenas para completar formulário.

Frente concluída antiga não é reformatada por rotina. Frente ativa sem `Modo:` adota GESTÃO como default até a persistência quando retomada.

## 4. Seleção de frente e FRONT_TREE

Não existe “frente atual” global.

Seleção de frente segue:
1. `front_id` ou contexto explícito do operador;
2. única frente inequivocamente aplicável;
3. em ambiguidade real, pedir a menor desambiguação.

Nunca escolher automaticamente a frente mais recente.

`tmp/active/FRONT_TREE.md` é índice navegacional derivado dos ACTIVE das frentes. Não é proprietário de modo, branch, HEAD, status, task, parentesco, retorno ou autorização.

Antes de escrever FRONT_TREE:
1. releia o índice atual e os ACTIVE relevantes;
2. derive a projeção navegacional;
3. compare-a com a projeção corrente;
4. escreva somente se a projeção mudou;
5. faça readback.

Staleness temporária é tolerável porque o índice não é autoridade. Em concorrência, rederive a partir dos ACTIVE em vez de sobrescrever cegamente.

Disparam atualização apenas mudanças projetadas pelo formato do índice, por exemplo presença/fechamento da frente, status, branch/HEAD exibidos ou topologia exibida. Mudanças internas não projetadas não justificam regravação.

Ao abrir frente filha:
1. escolha `front_id` novo, plano, seguro e único e crie `tmp/active/<front_id>/ACTIVE.md + PLAN.md` diretamente sob `tmp/active/`; nunca crie a pasta da filha dentro da pasta do pai;
2. registre `Frente-pai` e `Origem no pai`;
3. registre `Retorno ao concluir` somente quando não for o pai ou quando a explicitação for material;
4. altere o pai somente se seu estado operacional realmente mudar;
5. regenere FRONT_TREE somente se sua projeção mudar;
6. não execute efeito Git por derivação lógica.

Ao fechar e retornar:
1. consolide resultado durável nos proprietários adequados;
2. use o pai como retorno implícito, salvo `Retorno ao concluir` explícito;
3. reconcilie na frente de retorno somente o necessário para continuar;
4. mova a frente concluída para `tmp/completed/<front_id>/` enquanto ainda for útil, mantendo-a como filha imediata de `tmp/completed/`;
5. regenere FRONT_TREE sem o nó concluído quando sua projeção mudar;
6. não infira merge, PR, fechamento de branch ou outro efeito Git.

## 5. Preâmbulo operacional

Somente a resposta final visível ao operador, quando houver frente ativa, começa com:

`Modo: <GESTÃO|EXECUÇÃO> | Frente: <front_id> | Branch: <branch|não aplicável|não confirmado>`

Esse preâmbulo aparece uma única vez por resposta final. Não o emita em análise/raciocínio/thinking, mensagens intermediárias de progresso, chamadas ou resultados de ferramentas, mensagens de sistema ou qualquer outro bloco que não seja a resposta final ao operador.

A linha de task só aparece quando a interação corrente executou ou está relatando trabalho que avança materialmente a task corrente do PLAN. Não a exiba apenas porque existe uma task corrente no ACTIVE ou porque o modo é EXECUÇÃO.

Se o PLAN possui fases explícitas, use:

`Fase <X>/<Y> | Task <K>/<N> (<task_id>)`

Se o PLAN possui tasks, mas não fases explícitas, use somente:

`Task <K>/<N> (<task_id>)`

Omitir a linha de task em discussão, análise, planejamento, status, esclarecimento, pedido de autorização, escolha/retomada de frente ou qualquer resposta que não esteja executando a task corrente. Não fabrique uma fase sintética como `Fase 1/1` para plano sem fases.

Fontes:
- modo, front_id e branch: ACTIVE após aplicar eventual diretiva `MODO:`;
- task ID, quando a linha de task for aplicável: ACTIVE;
- fase e posição da task: PLAN;
- HEAD não precisa aparecer no preâmbulo, mas continua no ACTIVE como `HEAD observado` quando relevante.

Antes de montar a linha de task, valide compatibilidade entre ACTIVE e PLAN. Deriva mecânica inequívoca pode ser reconciliada; deriva que exige decisão não pode ser mascarada por preâmbulo consistente apenas na forma.

## 6. Próximo item

Ao receber “execute somente o próximo item”:
1. leia ACTIVE + PLAN;
2. valide a task corrente;
3. se ACTIVE estiver mecanicamente inconsistente, reconcilie com efeito real e use a primeira task pendente do recorte pedido;
4. não pule bloqueio silenciosamente;
5. execute exatamente uma task;
6. atualize status/evidência mínima no PLAN;
7. atualize ACTIVE;
8. pare.

Conversa anterior não define “próximo”.


## 7. Escrita segura e formato raw

Documentação operacional viva usa `.md` com MIME `text/markdown` ou `.txt` com MIME `text/plain`. Formato rico pode existir como snapshot/artefato, não como proprietário recorrente do estado operacional.

Antes de escrever:
- releia o arquivo corrente;
- reconcilie mudança concorrente ou efeito real relevante;
- use controle de revisão quando suportado;
- prepare exatamente o conteúdo textual pretendido.

A implementação deve usar algum mecanismo suportado que preserve bytes/texto e MIME adequados ao formato final. Staging, parâmetros de API, conversores, nomes de ações e workarounds de um conector específico pertencem à camada de ferramenta, não ao contrato do harness.

Depois de escrever:
1. confirme arquivo e MIME corretos;
2. faça readback integral do conteúdo final;
3. normalize somente BOM inicial, CRLF/CR para LF e, quando tecnicamente comprovado, diferença de um único newline terminal;
4. exija igualdade integral entre conteúdo pretendido e readback normalizado;
5. confirme ausência de duplicação, perda/adição de indentação, escapes, fences, listas, tabelas ou whitespace semanticamente relevante;
6. confirme ausência de amplificação não semântica de linhas/tamanho;
7. preserve idempotência: regravar conteúdo idêntico deve produzir o mesmo conteúdo normalizado;
8. remova temporários criados pelo mecanismo de transporte, quando houver.

Contagem de linhas, tamanho, marcadores, títulos ou amostragem são diagnóstico; não substituem igualdade integral.

Se o único caminho disponível alterar conteúdo semanticamente relevante, a escrita não está comprovada. Falha de ferramenta não é gate nem autorização adicional: para operação já autorizada, pode-se tentar no máximo um caminho alternativo que preserve o mesmo escopo e os invariantes acima. Persistindo a falha, mantenha o proprietário real como autoridade e reporte o bloqueio técnico sem fabricar sincronização.

## 8. Concorrência

Um escritor por frente é a regra preferida; não há lock global do Drive.

Se concorrência sobre a mesma frente for descoberta:
1. suspenda novas escritas;
2. releia ACTIVE/PLAN;
3. confronte com efeitos reais;
4. reconcilie task/evidência/próximo passo;
5. defina um único escritor antes de continuar.

Frentes diferentes podem avançar em paralelo se não disputarem o mesmo arquivo, checkout ou efeito externo. Drive separado por `front_id` não isola Git, banco, runtime ou infraestrutura.

## 9. Checkup de coerência

Checkup é operação pontual de transição, read-only por padrão. Não existe contador de mensagens, decisões, tempo, watchdog, arquivo próprio nem campo `último checkup`.

Gatilhos:
- antes de recomendar GESTÃO → EXECUÇÃO após deliberação material;
- depois de rebaseline ou mudança material de direção, antes de continuar trabalho dependente;
- antes de fechar fase ou frente;
- pedido explícito do operador.

Procedimento mínimo:
- reconfirmar objetivo/problema real;
- confrontar ACTIVE, PLAN, FRONT_TREE quando aplicável e fontes proprietárias afetadas;
- procurar contradição, premissa superada, scope creep, complexidade sem problema concreto e estado documental obsoleto;
- em fechamento, verificar também decisão superada competindo com corrente, duplicação, histórico que deve migrar para HISTORY/SUBPLAN e anomalia de whitespace/tamanho;
- se coerente, continuar sem criar registro;
- se houver delta material, tratá-lo pelo proprietário e autorização normais.

Checkup não muda modo, não renova autorização, não cria autorização nova e não é gate nem pré-condição universal para trabalho normal em EXECUÇÃO.

## 10. Handover

Handover é índice curto de retomada, não quarta memória. Quando necessário, contém somente `front_id`, motivo, caminhos exatos, fato excepcional difícil de reconstruir e limitação material ainda não refletida no proprietário. Retomada normal deve funcionar sem handover.

## 11. QA persistido

Checagens rápidas, comandos focais, inspeções e POCs pertencem ao desenvolvimento e não criam QA_ID/pacote/REPORT por padrão.

Rodadas persistidas de `CHECKPOINT` e `FORMAL` usam o mesmo mecanismo:
- `PACOTE_QA.txt` como pacote corrente;
- `RELATORIO_QA/` como slot publicado descartável da rodada corrente, não como arquivo histórico;
- `QA atual` no ACTIVE como reserva/continuidade.

A criação ou reemissão de `PACOTE_QA.txt` para um novo prompt de execução é fronteira de reset do slot publicado. Antes de gravar o pacote, a sessão controladora deve esvaziar todo o conteúdo de `RELATORIO_QA/`, preservando a própria pasta; se a pasta não existir, deve criá-la. Em seguida deve fazer readback e confirmar que o slot está vazio. Evidência anterior que ainda precise ser durável deve estar consolidada em PLAN/HISTORY antes da limpeza; `RELATORIO_QA/` não é arquivo de rodadas passadas.

Para nova rodada ou reemissão destinada a nova tentativa do executor:
1. releia ACTIVE e o estado real da frente;
2. reutilize `QA atual` quando estiver retomando a mesma rodada válida;
3. caso contrário, reserve o próximo `QA-H3-<front_id>-<NNN>`;
4. grave primeiro `QA atual` no ACTIVE e faça readback;
5. esvazie `RELATORIO_QA/`, mantenha a pasta e confirme por readback que ficou vazia;
6. crie/substitua `PACOTE_QA.txt` com o mesmo QA_ID, `CREATED_AT` atualizado em ISO 8601 com timezone e `RESULT_DESTINATION: .tmp/qa/run/result/`; faça readback;
7. não recicle número reservado após FAIL, BLOCKED, NOT RUN, cancelamento ou interrupção.

Retomada da mesma rodada sem criação/reemissão do pacote não limpa o slot novamente.

Bloqueio operacional recuperável não encerra a rodada. O mesmo QA_ID pode continuar depois de ação do operador quando escopo e revisão continuarem válidos.

O executor local não depende do Drive. O workspace local é único e efêmero por checkout em `.tmp/qa/run/`: uma nova sessão limpa todo `run/`, enquanto cada `preflight` limpa somente `run/result/`. Identidade da rodada permanece nos metadados (`front_id`, `QA_ID`), não no pathname. O protocolo e o contrato do pacote pertencem a `methodologies/QA_LOCAL.md`.

## 12. Backlog

`TODO.txt` e `IDEIAS_E_PENDENCIAS.md`, se mantidos na H3, ficam no Drive fora das frentes. Leitura é permitida; escrita, edição, priorização, conclusão, promoção ou remoção dependem do gate de `GOVERNANCA.md`.

## 13. Encerramento

Antes de encerrar fase ou frente, execute o checkup de coerência do marco.

Ao encerrar frente:
- PLAN contém síntese suficiente;
- ACTIVE deixa de apontar trabalho pendente;
- HISTORY existe somente se necessário;
- QA corrente está reconciliado;
- conhecimento durável foi promovido ao proprietário correto;
- a pasta pode ser movida para `tmp/completed/<front_id>/`.

Mover/arquivar frente é operação documental; não implica merge, PR, CI, BETA ou release.

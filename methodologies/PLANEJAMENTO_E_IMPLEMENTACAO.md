# Metodologia — Planejamento e Implementação de Fases

Estado: candidata V3.0.1.

Esta metodologia define a mecânica de planejamento e implementação quando houver planejamento formal. Comportamento deliberativo pertence a `Modos/GESTAO.md`; comportamento de execução pertence a `Modos/EXECUCAO.md`; autoridade e gates pertencem a `GOVERNANCA.md`.

Ela não torna PLAN pré-condição universal para toda solicitação em EXECUÇÃO e não redefine a semântica de imperativos, `CONCORDO`, `AUTORIZO` ou mudança de modo.

## 1. Planejar em GESTÃO, executar com contexto mínimo

Esta metodologia é consultada **em GESTÃO ao criar ou revisar plano de feature relevante**. Ela é uma ferramenta de qualidade de decisão; não é carregada por rotina em EXECUÇÃO, não exige formulário, documento separado, checklist persistente ou confirmação extra. Para ajuste pontual, aplicar apenas verificações pertinentes.

Antes de propor uma mudança, confrontar a necessidade com as fontes reais do produto (`PRODUCT_PROFILE`, documentação existente, código, contratos e testes relevantes). Não presumir que um componente não existe sem investigar. Distinguir comportamento desejado do estado implementado; não importar caminhos ou regras de outro projeto.

### 1.1 Autoavaliação interna de feature — nove dimensões

O agente realiza espontaneamente estas verificações, com profundidade proporcional ao impacto e à incerteza:

1. **Problema e objetivo:** o problema operacional, seus atores, resultado esperado e recorte estão claros?
2. **Investigação do existente:** foram examinadas funcionalidades, serviços, componentes, APIs, regras, dados e padrões que já resolvem parte do problema?
3. **Reuso e duplicidade:** é possível reutilizar/estender o existente? Criar algo novo duplicaria responsabilidade, interface, estado ou fonte de verdade?
4. **Requisitos e decisões vigentes:** a proposta respeita contratos, PRD/glossário quando disponíveis, arquitetura e decisões consolidadas?
5. **Alternativas e boas práticas:** alternativas realmente pertinentes foram avaliadas? A recomendação é a solução mais simples e sustentável que atende ao objetivo?
6. **Análise de impacto:** dependências e efeitos relevantes sobre código, UX, dados, banco, permissões, segurança, integrações, custo e operação foram verificados quando aplicáveis?
7. **Preservação e regressões:** o que funciona hoje e deve permanecer válido? Quais invariantes, consumidores e testes de regressão protegem esse estado?
8. **Plano incremental:** quais partes existentes serão aproveitadas, estendidas ou criadas? As tarefas têm limites, dependências e gates reais?
9. **Critérios de aceite:** o comportamento é verificável por cenários e evidências apropriadas, distinguindo teste local, CI, integração real e implantação?

Cada aspecto pode ser **verificado**, **não aplicável** ou **incerto**; não forçar nove afirmações públicas. Incerteza material deve gerar investigação ou ressalva, nunca certeza inventada. Somente divergência, alternativa superior, risco ou decisão material merecem destaque espontâneo ao operador.

### 1.2 Política de preservação

**Reutilizar primeiro; estender quando necessário; criar novo somente com justificativa.** Planeje o menor delta coerente, sem redesenhar fluxo estável por preferência técnica. Antes de alterar dados, APIs, interfaces ou regras, identifique consumidores, contratos, invariantes, histórico e risco de regressão. Se houve regressão recente, isole a causa e corrija-a sem eliminar melhorias posteriores.

Não prometa ausência de regressão: explicite validações proporcionais e limites de evidência. Guardas de segurança, gates e legado opt-in permanecem em `GOVERNANCA.md`.

### 1.3 Saída da GESTÃO e handoff

A saída normal é **recomendação principal e plano enxuto**, contendo apenas quando relevantes: objetivo, estado atual verificado e fonte, decisão, componentes concretos a reutilizar/estender, criação justificada, invariantes e dependentes, riscos, tarefas, limites, gates, aceite e testes de regressão. Guarde conclusões duráveis no `PLAN.md` ou no proprietário já existente.

**Não transportar** para EXECUÇÃO o checklist completo, histórico de opções descartadas, transcrição da deliberação ou V2.1 integral. A implementação recebe somente o resultado do planejamento e investiga localmente o necessário. Não criar `CHECKLIST.md`, plano paralelo ou nona memória.

## 2. Planejar o incremento

Mantenha no `PLAN.md`:
- objetivo observável;
- tasks suficientes para controlar execução;
- aceite verificável;
- dependências/gates;
- riscos materiais ainda úteis, invariantes/consumidores a preservar e componentes existentes a reutilizar quando governarem a execução;
- evidência mínima esperada.

Prefira fatias verticais pequenas e reduza integração tardia. Separe tasks quando domínio, migration/aplicação, grande refactor, UI, QA formal ou ativação/release tiverem gates/evidências diferentes.

Evite microtasks puramente mecânicas quando não melhorarem controle ou retomada.

`PLAN.md` possui tasks e status. `ACTIVE.md` contém apenas a task corrente e o presente operacional. Não crie CHECKLIST separado.

## 3. Aceitação e contratos

Defina cedo como o comportamento será comprovado:
- cenários de aceitação/BDD quando reduzirem ambiguidade;
- contratos técnicos e invariantes;
- regressões materiais;
- estados de erro/bloqueio;
- gates externos previsíveis.

Formato BDD útil quando aplicável:

```text
Dado <estado relevante>
Quando <ação>
Então <efeito observável>
```

Não force BDD em detalhe técnico sem comportamento relevante. Planejar um gate não autoriza executá-lo.

## 4. Implementar verticalmente

A cada task:
1. confirme branch/HEAD e o recorte técnico quando aplicável;
2. implemente o menor delta coerente;
3. use teste focal/experimento quando responder a incerteza real;
4. prefira checks baratos antes de QA formal;
5. registre no PLAN apenas evidência que feche a task, sustente decisão, explique regressão ou seja necessária para retomada;
6. atualize o presente operacional conforme `OPERACAO_DOCUMENTAL.md`.

Não introduza compatibilidade não autorizada nem mutação compartilhada por conveniência.

## 5. QA durante desenvolvimento

Use SUPPORT quando houver pergunta técnica concreta, reprodução/diagnóstico, teste focal, contrato específico ou inspeção visual focal.

PASS de SUPPORT orienta desenvolvimento e não fecha a feature.

Não abra QA por microtask. Quando o incremento estiver materialmente implementado, prepare FORMAL conforme risco/escopo e `methodologies/QA_LOCAL.md`.

Não repita full regression a cada incremento quando FAST/NORMAL cobrem o delta e houver fechamento de fase planejado.

## 6. Fechamento

Antes de concluir task:
- confirme efeito real;
- execute validação proporcional;
- compacte o PLAN para resultado/evidência/limite durável;
- atualize status no PLAN;
- atualize ACTIVE.

Antes de fechar feature/fase:
- confronte requisitos e implementação;
- confirme migrations escritas versus aplicadas;
- execute QA FORMAL aplicável;
- registre NOT RUN/BLOCKED honestamente;
- execute o checkup de coerência previsto em `OPERACAO_DOCUMENTAL.md`;
- não confunda QA local, CI, runtime, BETA e release.

## 7. Checkpoints de branch

Quando a frente tiver autorização explícita para criar branches/checkpoints, use a estratégia aprovada para a frente. Não crie branch por microtask.

Branch nova, merge, push que dispare CI e demais efeitos continuam sujeitos a `GOVERNANCA.md`.

## 8. Consolidação

Promova comportamento, conceito, arquitetura, design ou operação ao proprietário correspondente quando materialmente afetados.

Atualize STATUS_ATUAL somente por mudança material. PLAN preserva síntese suficiente; detalhes ficam em Git/QA/fontes proprietárias.

Planos orientam trabalho futuro e não substituem especificação nem estado implementado.

## 9. “Execute somente o próximo item”

A resolução determinística pertence a `OPERACAO_DOCUMENTAL.md`. Esta metodologia não mantém algoritmo concorrente.

# Metodologia — Planejamento e Implementação de Fases

Estado: candidata V3.0.1.

Esta metodologia define a mecânica de planejamento e implementação quando houver planejamento formal. Comportamento deliberativo pertence a `Modos/GESTAO.md`; comportamento de execução pertence a `Modos/EXECUCAO.md`; autoridade e gates pertencem a `GOVERNANCA.md`.

Ela não torna PLAN pré-condição universal para toda solicitação em EXECUÇÃO e não redefine a semântica de imperativos, `CONCORDO`, `AUTORIZO` ou mudança de modo.

## 1. Preparar o recorte

Antes de planejar ou implementar:
- identifique problema e resultado observável;
- identifique ator/jornada afetada quando houver;
- leia os requisitos/invariantes pertinentes do PRD/Glossário;
- confronte o estado implementado relevante;
- identifique dependências, permissões, dados e gates afetados;
- delimite o que está fora de escopo.

Não use plano, teste ou protótipo para redefinir produto silenciosamente.

## 2. Planejar o incremento

Mantenha no `PLAN.md`:
- objetivo observável;
- tasks suficientes para controlar execução;
- aceite verificável;
- dependências/gates;
- riscos materiais ainda úteis;
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

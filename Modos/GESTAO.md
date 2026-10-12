# Modo GESTÃO — Harness V3

## 1. Papel

GESTÃO é o regime deliberativo do harness: compreender, verificar, confrontar, recomendar e consolidar uma decisão antes de materializar mudanças duráveis.

GESTÃO e EXECUÇÃO possuem as mesmas capacidades técnicas e estão sujeitos aos mesmos gates. A diferença não é “poder escrever” versus “não poder escrever”; é onde a cognição e a interação se concentram. Em GESTÃO, o agente prioriza a qualidade da decisão antes da materialização.

A decisão material pertence ao operador. O agente forma avaliação própria, preserva o que funciona, procura a solução mais simples que resolva corretamente o problema e evita oposição artificial.

## 2. Ciclo deliberativo

Para uma nova direção relevante, use este ciclo como contrato semântico:

1. **compreender** — identificar problema real, objetivo, escopo e premissas;
2. **verificar** — confrontar fontes proprietárias, estado implementado e contexto necessário;
3. **confrontar** — avaliar coerência, duplicidade, impacto, alternativas e consequências;
4. **propor/recomendar** — apresentar uma direção principal e alternativas apenas quando puderem mudar materialmente a decisão;
5. **consolidar decisão** — tornar inequívocos o comportamento/recorte escolhido e a ação concreta pendente;
6. **autorizar** — para materialização durável em GESTÃO, obter `AUTORIZO` sobre a ação concreta pendente, sem dispensar gates independentes;
7. **materializar** — executar o recorte autorizado, incluindo microdecisões técnicas necessárias que não alterem a decisão material;
8. **validar/consolidar** — verificar o efeito proporcionalmente e reconciliar o proprietário adequado quando houver estado durável.

O ciclo não é um rito. Etapas triviais podem ser breves e não exigem mensagens ou documentos separados. Uma interação pode terminar em análise, recomendação ou definição sem obrigação de chegar à materialização.

## 3. Avaliação crítica proporcional

Toda nova direção relevante em GESTÃO recebe avaliação crítica explícita antes da materialização.

A profundidade é proporcional ao impacto e à incerteza:

- se a direção estiver adequada e não houver alternativa materialmente melhor, a avaliação pode ser breve e concluir que não há objeção material;
- se risco concreto, inconsistência ou alternativa materialmente melhor puder mudar o que será construído, explique a consequência, recomende uma direção principal e peça somente a decisão necessária;
- se a diferença for local, reversível ou praticamente equivalente, resolva como detalhe técnico e não devolva a escolha ao operador.

Não invente contrapontos, riscos ou opções apenas para demonstrar criticidade. Não reabra decisão conscientemente tomada sem fato novo material.

## 4. Comandos e fronteira de materialização

Pedido ou imperativo comum em GESTÃO expressa direção/intenção e inicia ou continua a deliberação. Por si só, não autoriza edição persistente, implementação ou outro efeito material.

Quando a deliberação estiver madura, proponha de forma natural a ação concreta que pode ser materializada e seu recorte.

`CONCORDO`, como resposta explícita e inequívoca, aprova a última proposta concreta aplicável. Não materializa, não muda o modo e não satisfaz gate independente.

`AUTORIZO`, como resposta explícita e inequívoca, autoriza a materialização da última ação concreta pendente e implica concordância com esse recorte. A autorização vale somente para o escopo proposto e nunca supera `GOVERNANCA.md`.

O recorte autorizado inclui detalhes locais, reversíveis e tecnicamente equivalentes necessários para completar a ação, além de validação proporcional e atualização operacional permitidas. Não exija confirmação arquivo por arquivo nem para microdecisões que preservem a decisão material.

`AUTORIZO` não cobre decisão material nova surgida depois da autorização. Fato novo material interrompe somente o recorte dependente.

Se houver múltiplas ações concretas pendentes ou alcance ambíguo, peça apenas a desambiguação necessária.

Diretiva de modo é independente: `AUTORIZO` não muda automaticamente para EXECUÇÃO, e `MODO: EXECUÇÃO` não substitui `AUTORIZO` para uma materialização ainda pendente em GESTÃO.

## 5. Decisão material

Uma decisão é material quando altera comportamento, contrato, arquitetura, segurança, persistência, custo, autoridade, gate ou obrigação percebida por usuário, produto, outro sistema ou fonte proprietária.

Detalhe local e reversível que preserve esses limites é microdecisão técnica e pode ser resolvido pelo agente dentro do recorte autorizado.

Quando uma decisão posterior superar regra anterior, o delta deve ser reconciliado no proprietário adequado antes de virar estado durável.

## 6. Transição e checkup

GESTÃO não troca de modo autonomamente.

Quando a deliberação estiver suficientemente consolidada e o trabalho subsequente for predominantemente de realização, o agente pode recomendar `MODO: EXECUÇÃO`. Somente diretiva explícita do operador altera o modo persistente.

GESTÃO pode materializar uma ação depois de `AUTORIZO` sem mudar de modo. Troca de modo não é gate técnico.

Antes de uma transição GESTÃO → EXECUÇÃO após deliberação material, e antes de fechamento de fase/frente, use somente o checkup curto definido em `OPERACAO_DOCUMENTAL.md`. Checkup não autoriza, não muda modo e não substitui gate.

## 7. Limites

Autoridade, gates, segurança, legado e níveis de evidência pertencem a `GOVERNANCA.md`. Mecânica de frente e escrita operacional pertence a `OPERACAO_DOCUMENTAL.md`.

GESTÃO não transforma recomendação em autorização, não escolhe silenciosamente entre fontes proprietárias conflitantes e não amplia o recorte autorizado por conveniência.

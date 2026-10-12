# Metodologia — Evolução de Interface e Validação Visual


Estado: candidata V3.0.1.


## 1. Objetivo


Evoluir UI preservando a jornada real, estados operacionais, responsividade, acessibilidade e contratos funcionais.


Validação visual não substitui teste de comportamento; teste funcional não substitui inspeção de composição quando a mudança é visual.


## 2. Antes de alterar


Entenda:
- objetivo da tela;
- ator e jornada;
- estado vazio, carregando, sucesso, erro, desabilitado e permissão negada;
- navegação/retorno;
- dados reais que definem tamanho e densidade;
- breakpoints relevantes;
- padrões/componentes já existentes.


Leia o recorte funcional do PRD/Glossário quando a UI representar regra de domínio.


Não redesenhe fluxo apenas por preferência estética.


## 3. Escopo


Mudança cosmética local pode ser tratada com contexto pequeno.


Mudança material de layout, navegação, hierarquia, interação ou estado exige:
- contexto funcional;
- comparação com padrão existente;
- validação da jornada afetada;
- atenção a responsividade e estados alternativos.


Se uma alternativa estruturalmente melhor mudar materialmente a jornada, trate o fato como decisão material segundo o contrato do modo ativo. Esta metodologia define o impacto de interface; `Modos/` define quando deliberar, pedir decisão ou materializar.


## 4. Implementação


Prefira:
- componentes existentes;
- tokens/estilos já usados;
- estrutura semântica simples;
- estados explícitos;
- feedback de ação claro;
- mensagens orientadas ao usuário.


Evite:
- duplicar componente para variação trivial;
- hardcode de dimensões que quebre dados reais;
- overlay/z-index como correção permanente de estrutura ruim;
- esconder erro operacional sem alternativa compreensível.


## 5. Validação


SUPPORT visual durante desenvolvimento pode validar um recorte.


Para mudança material, verifique conforme aplicável:
- estado principal;
- loading;
- vazio;
- erro;
- desabilitado;
- confirmação/sucesso;
- navegação ida/volta;
- viewport menor e maior relevantes;
- conteúdo longo;
- permissões/feature flags relevantes.


Screenshots são evidência complementar.


## 6. Browser e recursos


Browser/profile compartilhado que possa interferir é `EXCLUSIVE_RESOURCE`.


Não mate processo de outra instância.


Portas locais vêm de `config.yaml`; não presuma defaults quando a configuração estiver disponível.


## 7. Evidência


Registre somente o necessário para provar a jornada/estado.


Imagem pesada, vídeo e logs ficam como artifact referenciado, não dentro de ACTIVE/PLAN.


No FORMAL, o REPORT deve distinguir comportamento executado de inspeção visual.
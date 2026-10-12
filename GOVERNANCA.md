# GOVERNANCA.md — Harness V3

## 1. Papel e autoridade

Este arquivo é proprietário somente de autoridade, gates, segurança, legado e níveis de evidência. Comportamento de GESTÃO/EXECUÇÃO pertence a `Modos/`; operação da frente pertence a `OPERACAO_DOCUMENTAL.md`; QA pertence a `methodologies/QA_LOCAL.md`.

A definição do harness vem do Git no SHA exato fixado pela frente em `Harness ref`. Estado operacional mutável da frente vive no workspace definido para o projeto. Recuperação e manutenção da linha `harness` pertencem a `docs/RECUPERACAO_E_VERSIONAMENTO.md`.

No `PRODUCT_REPOSITORY`, caminhos para documentos de requisitos, terminologia, status e convencoes locais sao opcionais e pertencem ao `PRODUCT_PROFILE`. Se um caminho nao foi configurado ou o arquivo nao existe, nao invente seu conteudo nem use caminhos fixos de outros produtos. Codigo, testes e configuracoes do produto evidenciam o implementado. Perfil local nunca altera gates de governanca do core.

Decisão posterior explicitamente aprovada pode superar definição anterior, mas o delta deve ser reconciliado no proprietário adequado antes de virar estado durável.

Não existe precedência global por data. Conflito material entre proprietários legítimos bloqueia somente a ação afetada até reconciliação.

## 2. Legado opt-in

Legado e compatibilidade retroativa não são requisitos implícitos.

Enquanto o projeto estiver em BETA, não introduza preservação de dados/estados antigos, compatibilidade, backfill, fallback, cutover, downgrade defensivo ou mecanismo equivalente apenas porque uma versão anterior existiu em DEV.

Antes de criar essa obrigação, consulte o operador explicitamente. Silêncio, dados existentes, migration antiga, teste histórico, branch anterior ou snapshot não constituem autorização.

Isso não remove invariantes atuais de produto, como imutabilidade, auditoria, linhagem ou reprodutibilidade, quando definidos pelas fontes proprietárias vigentes.

Preferir modelo atual limpo não autoriza reset, migration ou mutação compartilhada.

## 3. Gates

Os gates abaixo são ortogonais aos modos. A mesma ação recebe o mesmo tratamento em GESTÃO e EXECUÇÃO; mudar de modo não concede nem remove autorização. Os contratos de modo podem exigir uma etapa deliberativa ou uma semântica de comando antes da materialização, mas não redefinem nem satisfazem estes gates.

Permitido dentro do escopo já autorizado:

- ler Drive, código, branches, diffs, commits, PRs, runs, jobs, logs e artifacts existentes;
- implementar, corrigir e criar commits sobre branch já autorizada;
- publicar commits por push ou atualizar a ref remota de branch já autorizada, desde que isso não provoque outro efeito gated não autorizado;
- executar teste focal ou experimento local/descartável permitido;
- atualizar o estado operacional da frente.

Exige autorização explícita prévia:

- criar branch local ou remota;
- fazer merge;
- abrir novo PR;
- executar GitHub Actions/CI ou provocar evento que as dispare;
- escrever, concluir, priorizar ou remover item de TODO/IDEIAS;
- abrir, incrementar ou fechar BETA;
- criar tag, versão oficial ou release;
- aplicar/reverter migration ou mutar banco, runtime ou infraestrutura compartilhados;
- introduzir custo recorrente, serviço pago ou infraestrutura adicional.

Autorização vale somente para o conjunto identificado; não é ampliada por histórico, conveniência ou proximidade de escopo.

Antes de push, atualização de ref ou PR, verifique triggers reais. Push/atualização de ref não exige autorização própria; se a publicação disparar CI ou outro efeito gated, esse efeito continua exigindo autorização.

Atualizar estado operacional não autoriza criar branch, merge, PR, CI, backlog, BETA, release ou mutação compartilhada.

## 4. Segurança e integridade

Não hardcode nem publique segredos.

Não enfraqueça Permission/Scope, isolamento, credenciais, auditoria ou invariantes para fazer implementação ou teste passar.

Antes de exclusão física ou ação destrutiva, confronte as regras proprietárias e alternativas aplicáveis.

Mudança persistida exige migration versionada quando aplicável. Migration escrita não é migration aplicada.

Não introduza infraestrutura, dependência ou custo recorrente apenas por conveniência operacional.

## 5. Evidência e estados independentes

Distinguir:

- analisado/definido;
- implementado;
- validado localmente;
- validado em CI;
- validado em runtime real;
- implantado;
- checkpoint BETA;
- release.

Nenhum estado implica automaticamente o seguinte.

Resultado verde comprova somente o nível realmente exercitado. Para saber o que ocorreu, use efeito observável; para comportamento durável, reconcilie o proprietário correto.

## 6. BETA e release

Término de feature/fase, QA, commit, push, merge, PR ou CI verde não autoriza BETA ou release.

Checkpoint BETA e release são estados distintos. Release oficial depende de autorização específica e implantação efetiva quando aplicável.

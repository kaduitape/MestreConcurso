# Evolução com agentes inteligentes — diagnóstico, plano e riscos

> Documento de decisão, anterior a qualquer código. Responde ao pedido
> "apresente um diagnóstico da arquitetura, um plano de evolução e os riscos
> identificados".

## Resumo executivo

A plataforma pedida **já existe em grande parte**. Do que o pedido descreve,
por volta de **70% está construído e em produção**: o cadastro de concursos, a
análise de editais com evidência rastreada, a inteligência estatística, o
Estúdio de Treinamento, os flashcards com repetição espaçada, a Batalha RPG, o
tutor, o plano de estudo e a gamificação.

O trabalho real não é construir oito agentes. É:

1. **Amarrar o conteúdo à hierarquia do edital** (hoje a aula não sabe de qual
   tópico ela é — ver [Lacuna 1](#lacuna-1--a-aula-não-sabe-de-qual-tópico-é)).
2. **Criar o orquestrador** que já falta para a análise de edital e que vai
   faltar para tudo que vier depois.
3. **Criar o auditor** (Agente 7) e o **analista de melhorias** (Agente 8), que
   não existem em nenhuma forma.
4. **Decidir o papel do JEV**, que não é o que o pedido supõe.

Escrever oito agentes do zero duplicaria código que já roda, já tem teste e já
tem dado em produção. O pedido proíbe isso, e com razão.

---

## 1. Diagnóstico por módulo

Legenda: **✅ pronto** · **🟡 parcial** · **⬜ não existe**

### Módulo 1 — Administração centralizada dos concursos

| Item pedido | Estado | Onde |
|---|---|---|
| Nome, órgão, cargo, banca, ano | ✅ | `competitions`, `positions`, `organizations`, `exam_boards` |
| Edital em PDF + complementares | ✅ | `notices`, `notice_files` |
| Remuneração, vagas, requisitos | ✅ | `notice_facts` com nível de evidência |
| Datas de inscrição e provas | ✅ | `notice_events` |
| Disciplinas, tópicos, subtópicos | ✅ | `notice_subjects`, `notice_topics`, `subjects`, `topics` |
| Pesos e critérios | ✅ | `notice_facts` (`exam.*`) |
| Conteúdos gerados pelos agentes | 🟡 | existem, mas **sem vínculo estrutural** — Lacuna 1 |
| Histórico de alterações e retificações | 🟡 | `NoticeKind.RECTIFICATION` existe; falta o diff e o reprocessamento |
| Status rascunho→publicado | 🟡 | `NoticeStatus` tem 6 estados, mas não os do pedido |
| Permissões por plano | ✅ | `entitlements`, `billing/quota` |

**Isolamento de dados por usuário: ✅ resolvido.** 19 tabelas carregam
`user_id`; progresso, tentativas, flashcards, XP, batalhas, metas e cronograma
já são por usuário. O conteúdo acadêmico (questões, aulas, mapas) é global e
não é duplicado por aluno. A arquitetura pedida nesse ponto **já é a que está
no ar**.

**O que falta de verdade:** o usuário não declara "meu concurso". O vínculo
existe só dentro do `study_plans.competition_id`. Não há um conceito de
*concurso principal* no perfil, que o Módulo 5 pede no painel.

### Módulo 2 — Central de Integrações de IA

| Item | Estado | Onde |
|---|---|---|
| Configurar provedores e chaves | ✅ | `ai_providers`, chave **criptografada**, nunca no navegador |
| AISA.one | ✅ | `app/ai/providers/aisa.py` |
| Modelos disponíveis + sincronização | ✅ | `ai_models`, `/models/sync` |
| Teste de conectividade | ✅ | `/providers/{slug}/test`, com status persistido |
| Logs e histórico | ✅ | `ai_usage`, `audit_logs` |
| Prioridade por tarefa | 🟡 | `AIFeature` + `ai_feature_bindings` fixam **um** modelo por tarefa |
| Limites de consumo e orçamento | 🟡 | há cache e contagem de token; **não há teto nem corte** |
| Integração JEV | ⬜ | ver [seção 2](#2--o-jev-não-é-o-que-o-pedido-supõe) |
| Roteador de modelos | ⬜ | não existe |

Hoje existem **11 tarefas de IA** registradas (`notice.extraction`,
`question.classify`, `error.classify`, `board.profile`, `chat.tutor`,
`flashcard.generation`, `embeddings.default`, `rerank.default`,
`training.script`, `training.narration`, `mindmap.generation`), cada uma com
provedor e modelo escolhidos no painel, cache por impressão digital e
auditoria. **A fundação do roteador já está posta** — falta a decisão.

### Módulo 3 — Orquestrador de agentes

⬜ **Não existe de forma geral.** Existe uma instância específica: o pipeline de
análise de edital, com 7 passos persistidos e acompanháveis ao vivo
(`analysis_progress.py`: `read → extract → structure → index → ai → verify →
persist`), cada um com status, erro e motivo de pulo.

Existe também **Celery com 3 filas** (`default`, `notifications`,
`documents`), beat agendado e tasks de manutenção, cobrança e e-mail.

Ou seja: **o padrão e a infraestrutura existem; falta generalizar.** O
orquestrador pedido é o `analysis_progress` promovido a cidadão de primeira
classe, com dependências entre agentes, tentativas, limites de custo e execução
manual.

### Agentes 1 a 6 — já existem em produção

| Agente | Estado | Onde | Observação |
|---|---|---|---|
| **1 — Analista de editais** | ✅ | `notice_analysis.py`, `radiography.py` | Extrai, estrutura, data, peso; **confere cada citação no PDF** e rebaixa para `INFERRED` o que não confere. Não inventa. |
| **2 — Inteligência estatística** | ✅ | `intelligence/incidence.py`, `priority.py` | Já calcula confiança **a partir do tamanho da amostra** e separa frequência de estimativa. |
| **3 — Professor** | ✅ | `services/training.py`, `mindmap.py`, `vocabulary.py` | Aulas em cenas, narração com direção de cena, mapas mentais, vocabulário, vídeos verificados. |
| **4 — Memorização** | ✅ | `services/flashcards.py`, `domain/srs/` | Repetição espaçada com fila e agendador. |
| **5 — Mestre de batalhas** | ✅ | `domain/game/battle*.py` | 3 fases, chefes, campanha, classes, equipamento, ranking. |
| **6 — Tutor adaptativo** | ✅ | `services/tutor.py`, `study_plan.py`, `analytics/master_score.py` | Mestre Score **já é separado do XP**, como o pedido exige. |

O pedido do Agente 2 — "nunca inventar porcentagens", "exibir tamanho da
amostra, origem e metodologia" — **já é a regra implementada**. O do Agente 6 —
"não usar somente XP para medir aprendizagem" — também: o XP é proibido de
alimentar o Mestre Score desde a fase de gamificação.

### Agente 7 — Auditor de qualidade

⬜ **Não existe como agente.** Existem controles espalhados que fazem parte do
trabalho dele:

- Verificação de citação contra o PDF (análise de edital).
- Validação estrutural de roteiro e de mapa mental, com recusa.
- Revisão humana obrigatória antes de publicar (aula e mapa ficam em `READY`).
- `trap_patterns` (catálogo de pegadinhas).

Falta o que o pedido descreve: revisão **cruzada** do conteúdo de um agente por
outro, conferência de gabarito, detecção de duplicata e ambiguidade, bloqueio
de publicação e histórico de correções.

### Agente 8 — Analista de melhorias

⬜ **Não existe nada.** É o item de maior risco do pedido inteiro — ver
[Risco 4](#risco-4--o-agente-8-é-o-mais-perigoso-do-pedido).

### Módulos 4 e 5 — Gamificação e painel

| Item | Estado |
|---|---|
| Níveis, XP, conquistas, missões | ✅ `domain/game/` (levels, ranks, missions, achievements, streak) |
| Classes e habilidades | ✅ `battle.py` (4 classes, 9 equipamentos por conquista real) |
| Chefes por disciplina | ✅ `board_battle.py`, `battle_campaign.py` |
| Ranking competitivo opcional | ✅ com anonimato e opção de sair |
| Mapas de progressão | ✅ `journey.py`, `territory.py` |
| Inventário visual | 🟡 equipamento existe; falta a tela de inventário |
| Árvore de conhecimento | ⬜ não existe |
| Painel do aluno | 🟡 existe (`analytics/dashboards.py`, Hoje); falta *concurso principal* e *dias restantes* |
| Redução de movimento | ✅ `useReducedMotion` respeitado |

---

## 2 — O JEV não é o que o pedido supõe

Você pediu para eu verificar a documentação real antes de implementar, e para
não presumir orquestração, escolha automática de modelos ou pesquisa externa.
**A ressalva estava certa.**

### O que o JEV é

O **Jev**, da **TypeSafe AI**, é um modelo de decisão ("System One"). Ele **não
gera texto**. Ele responde **perguntas tipadas sobre um estado** que a aplicação
fornece, devolvendo **probabilidade calibrada** em vez de prosa:

- **boolean** — sim/não com probabilidade de 0 a 1;
- **choice** — escolha entre opções que você define;
- **score** — nota numa escala que você define, com legenda e probabilidade por
  nível.

### O que o JEV não faz

Não orquestra agentes. Não escolhe modelos sozinho. Não pesquisa na internet.
Não escreve aula, questão, flashcard nem mapa mental. **Nenhuma das capacidades
que o Módulo 2 e o Módulo 3 atribuem a ele.**

### Onde ele serve de verdade

Isso não o torna inútil — torna-o certo para **outro lugar**, e um lugar que o
projeto precisa:

- **Agente 7 (auditor):** "este gabarito está correto?" (boolean com
  probabilidade), "esta questão pertence a qual tópico do edital?" (choice),
  "qual a qualidade desta explicação, de 0 a 5?" (score). Saída tipada e
  calibrada é exatamente o que um portão de qualidade precisa — e é melhor que
  pedir a um LLM generativo para julgar em prosa.
- **Roteador de modelos:** decidir a faixa de modelo por complexidade de tarefa
  (choice), em vez de uma regra fixa.
- **Gate de confiança:** transformar "a IA achou" em um número auditável.

### O que eu não consigo confirmar daqui

A documentação oficial (`docs.typesafe.ai/api`) **não abre deste contêiner** —
DNS bloqueado pela política de rede do ambiente. O que descrevi acima vem de
fontes independentes, e **elas divergem em detalhes do protocolo**: o tipo da
pergunta sim/não aparece como `boolean` em umas e `noul` em outras, e o caminho
`/v1/evaluate` não está confirmado.

**Por isso não vou escrever o adaptador do JEV com o protocolo adivinhado.** Um
adaptador escrito em cima de documentação de terceiros divergente é exatamente
o tipo de integração inventada que o seu pedido proíbe. Preciso de uma destas
três coisas:

1. você colar aqui a referência da API (`docs.typesafe.ai/api`); ou
2. liberar o domínio na política de rede do ambiente; ou
3. a chave + um exemplo de chamada que funcione na sua conta.

Até lá, o desenho prevê o JEV como **porta separada** (`DecisionProvider`), não
como mais um `AIProvider` — porque o contrato é outro: pergunta tipada e
probabilidade, não mensagem e texto.

Fontes: [Vercel AI Gateway — Jev](https://vercel.com/changelog/ai-gateway-now-supports-typesafe-clients-and-http-api-for-jev) ·
[AI SDK — provider TypeSafe](https://ai-sdk.dev/providers/ai-sdk-providers/typesafe-ai) ·
[Cloudflare Workers AI — Jev](https://developers.cloudflare.com/ai/models/typesafe/jev/) ·
[Langfuse — usando Jev para evals](https://langfuse.com/blog/2026-09-18-using-typesafes-jev-for-evals) ·
[TypeSafe — API reference](https://docs.typesafe.ai/api) (não acessível deste ambiente)

---

## 3 — As lacunas reais

### Lacuna 1 — A aula não sabe de qual tópico é

A mais importante, e a que mais trabalho gera se for deixada para depois.

| Conteúdo | Vínculo com o catálogo |
|---|---|
| Questão | ✅ `subject_id` + `topic_id` |
| Flashcard | ✅ `subject_id` + `topic_id` |
| Mapa mental | 🟡 tem `subject_id`, mas **nunca é preenchido**; `topic` é texto livre |
| **Aula (Dia de Treinamento)** | ❌ `subject` e `topic` são **texto livre**, sem FK |

Isso quebra três coisas que o pedido exige:

- **Módulo 6:** "ao atualizar um edital, regenerar somente os conteúdos
  afetados" — impossível, porque não dá para saber quais aulas pertencem ao
  tópico retificado.
- **Módulo 1:** "progresso por disciplina e tópico" não inclui aulas.
- **Módulo 5:** "domínio por tópico" fica cego para o que foi estudado em aula.

O mapa mental é dívida minha: eu criei o campo `subject_id` na fase passada e
não o preenchi. Está anotado.

### Lacuna 2 — Não existe "meu concurso"

O usuário não declara um concurso principal. O painel pedido no Módulo 5
("concurso principal", "dias restantes para a prova") não tem de onde ler.

### Lacuna 3 — Orquestração só existe para edital

Cada fluxo novo de IA refaz à mão o controle de progresso, erro e retentativa.

### Lacuna 4 — Sem teto de custo

Há contagem de token e cache, mas **nada corta** quando o orçamento estoura. O
Módulo 2 pede limite e o Módulo 7 pede monitoramento de custo.

### Lacuna 5 — Retificação não reprocessa

`RECTIFICATION` existe como tipo de arquivo, mas nada compara versões nem marca
o que mudou.

### Lacuna 6 — Nenhuma auditoria cruzada

Nada confere o gabarito de uma questão gerada contra o conteúdo da aula.

---

## 4 — Riscos

### Risco 1 — Reescrever o que já funciona

O maior risco do pedido. Ele descreve oito agentes como se fossem novos; seis
existem, com teste e dado em produção. Implementá-los "do zero" destruiria
trabalho validado.

**Mitigação:** cada agente novo é um **nome e uma porta** sobre o serviço que já
existe, não uma reimplementação. O "Agente 3" passa a ser um invólucro de
`TrainingService`, não um substituto.

### Risco 2 — Migração do vínculo de conteúdo (Lacuna 1)

Preencher `subject_id`/`topic_id` nas aulas existentes exige casar texto livre
com o catálogo. Casamento automático **vai errar**.

**Mitigação:** migração aditiva (coluna nova, nullable), casamento sugerido com
confirmação humana no painel, e nada apagado. Aula sem vínculo continua
funcionando como hoje.

### Risco 3 — Custo de IA sem teto

Gerar aula, mapa, flashcard e questão para **todas** as disciplinas de um edital
é um volume de token que ninguém mediu. Um edital grande pode custar caro em
uma única execução.

**Mitigação:** teto por execução e por mês **antes** de ligar a geração em
massa; estimativa exibida e confirmada antes de disparar; geração incremental
por tópico, não por edital inteiro.

### Risco 4 — O Agente 8 é o mais perigoso do pedido

Um agente que "produz propostas de alteração de código" é, na prática, um
agente com acesso ao repositório. O pedido já manda não permitir alteração
autônoma em produção — concordo, e vou além:

- ele **não** terá credencial de escrita no repositório;
- a saída dele é **texto e diff em anexo**, revisável, nunca um commit;
- não roda com acesso ao banco de produção.

Sugiro deixá-lo por último, e discuto o desenho antes de escrever uma linha.

### Risco 5 — Prompt injection via PDF

Já tratado no fluxo de edital (o conteúdo do PDF nunca vira instrução). O risco
**volta** a cada fonte externa nova que os agentes consumirem.

### Risco 6 — Conteúdo de IA publicado sem revisão

Hoje aula e mapa param em `READY` e exigem uma pessoa. Gerar em massa cria
pressão para "aprovar tudo". O Agente 7 existe para isso, e precisa vir **antes**
da geração em massa, não depois.

### Risco 7 — Dependência não fixada

`sqlalchemy` sem teto no `pyproject.toml` (pendência aberta desde 15/10). Cada
deploy resolve a versão que estiver publicada.

---

## 5 — Plano de evolução

Reordenei duas coisas em relação à sua sequência, e explico por quê.

### Fase 1 — Fundação do conteúdo (a que destrava todo o resto)

1. `subject_id` + `topic_id` em aulas e mapas mentais, aditivo e nullable.
2. Tela de vínculo no painel: sugestão automática, confirmação humana.
3. Concurso principal no perfil do usuário + dias restantes.
4. Status de concurso do pedido (rascunho → processamento → revisão →
   publicado → arquivado), sobre o `NoticeStatus` existente.

**Por que primeiro:** sem isso, nada que vier depois consegue dizer "este
conteúdo é deste tópico" — e o reprocessamento incremental do Módulo 6 fica
impossível.

### Fase 2 — Orquestrador + teto de custo

5. Generalizar `analysis_progress` em orquestrador: agentes, dependências,
   tentativas, limite de tempo e custo, execução manual, acompanhamento ao vivo.
6. Teto de custo por execução e por mês, com corte efetivo.
7. Registro dos 8 agentes como portas sobre os serviços existentes.

**Por que o teto aqui e não depois:** ligar geração em massa sem corte é a
forma mais rápida de transformar um erro em prejuízo.

### Fase 3 — Auditor (Agente 7) **antes** da geração em massa

8. Auditor com regras determinísticas primeiro (duplicata, gabarito ausente,
   alternativa repetida, tópico fora do edital).
9. Bloqueio de publicação e histórico de correções.
10. **Se** o JEV estiver confirmado: julgamento tipado com probabilidade.

**Por que antes:** você inverteu — na sua sequência a auditoria vem na Fase 2 e
a geração na Fase 3, o que está certo. Estou só reforçando: **nenhuma geração
em massa antes do portão existir.**

### Fase 4 — Geração em massa por tópico

11. Gerar aula, mapa, flashcard e questão **por tópico do edital**, incremental,
    com estimativa de custo confirmada antes de disparar.
12. Deduplicação e reaproveitamento entre concursos da mesma banca.

> Entregue em partes: aula e mapa mental na
> [parte 1](32-fase4-geracao-em-massa.md); o baralho oficial de flashcards e o
> agente de memorização na [parte 2a](39-fase4-parte2a-baralho-oficial.md). A
> geração de questões (agente *mestre de batalhas*) é a parte 2b e segue
> pendente: falta gerar questão com gabarito validado na origem.

### Fase 5 — Retificação e reprocessamento

13. Diff entre versões de edital; marcar o que mudou; regenerar só o afetado.

### Fase 6 — Roteador de modelos e JEV

14. Roteador configurável e auditável.
15. Adaptador `DecisionProvider` para o JEV, **com a documentação em mãos**.

### Fase 7 — Árvore de conhecimento e inventário

16. Os dois itens de gamificação que faltam.

### Fase 8 — Agente 8, com desenho discutido antes

---

## 6 — Critérios de aceite

Por fase, verificáveis:

- **F1:** toda aula criada pelo estúdio nasce com tópico vinculado; aula antiga
  sem vínculo continua abrindo; o painel mostra concurso principal e dias
  restantes a partir de dado real (sem data no edital → sem contagem, com o
  motivo escrito).
- **F2:** um agente que falha não trava os outros; o custo estourado **corta** a
  execução e registra; o administrador acompanha passo a passo ao vivo.
- **F3:** questão com gabarito ausente, alternativa duplicada ou tópico fora do
  edital **não publica**; cada bloqueio tem motivo legível e histórico.
- **F4:** gerar o mesmo tópico duas vezes não chama a API de novo; a estimativa
  de custo aparece antes e o valor real depois.
- **F5:** retificar um edital marca os conteúdos afetados e **não** regenera os
  demais.
- **F6:** a escolha de modelo é auditável — dá para dizer por que aquele modelo
  foi usado naquela execução.

---

## 7 — O que eu não vou fazer sem a sua confirmação

1. **Adaptador do JEV** com protocolo adivinhado — preciso da documentação.
2. **Casamento automático** de aulas antigas com o catálogo sem revisão humana.
3. **Geração em massa** antes do teto de custo e do auditor existirem.
4. **Agente 8** antes de discutir o desenho com você.

---

## 8 — Pendência anterior, ainda aberta

`sqlalchemy` sem limite superior em `backend/pyproject.toml`. Sugiro fixar
`<2.1` ou adotar lockfile antes de qualquer fase nova.

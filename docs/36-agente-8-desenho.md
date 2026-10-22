# Agente 8 — analista de melhorias: desenho para aprovação

> Documento de decisão, **anterior a qualquer código**. O plano em
> [27-evolucao-agentes-diagnostico.md](27-evolucao-agentes-diagnostico.md)
> classificou este agente como o item de maior risco do pedido inteiro e
> deixou combinado discutir o desenho antes de escrever uma linha. É o que
> está aqui. Nada foi implementado.

## 1. O que o pedido pede, e o que isso implica

O pedido descreve o Agente 8 como quem *"analisa o funcionamento da plataforma
e propõe melhorias"*, incluindo **propostas de alteração de código**, e manda
não permitir modificação autônoma em produção.

A segunda parte é a que define o desenho. Um agente que produz alteração de
código é, na prática, um agente com acesso ao repositório — e um agente com
acesso ao repositório é a maior superfície de risco que este projeto já
considerou, maior que o teto de custo e maior que a geração em massa. Se ele
errar, erra no lugar onde tudo o mais é construído.

Por isso o desenho abaixo começa pelos limites, não pelas capacidades.

## 2. Diagnóstico: o que ele pode consumir hoje

Cinco fases construíram, sem que fosse o objetivo, exatamente o material que
um analista precisa. Nada aqui precisa ser criado:

| Fonte | O que ela já registra | Fase |
|---|---|---|
| `ai_usage` | custo, tokens, latência, status, código de erro e cache de cada chamada de IA | 2 |
| `ai_routing_decisions` | por que cada modelo foi escolhido, com o rastro de cada regra | 6 |
| `ai_cache_entries` | acertos de cache e tokens economizados | 2 |
| `agent_runs` / `agent_steps` | passos do orquestrador, tentativas, falhas e pulos com motivo | 2 |
| `content_audits` | laudos por conteúdo, com achado por regra e o que ficou `NOT_CHECKED` | 3 |
| `content_audit_rules` | quais regras estão ligadas e com que severidade | 3 |
| `generation_plans` / `generation_items` | o que foi gerado, reaproveitado, falhou ou foi barrado por teto | 4 |
| `notice_diffs` | conteúdo que ficou órfão ou faltando depois de uma retificação | 5 |
| árvore de conhecimento | tópicos do edital sem vínculo e sem material, por disciplina | 7 |
| `question_attempts` | acerto real por questão e por tópico | 5/6 |
| `audit_logs` | o que cada administrador mudou e quando | 1 |

**O que não existe e seria preciso criar:** registro de *recusa* de recurso. A
plataforma recusa um simulado por falta de questões (`no_questions_available`)
e recusa uma resposta do tutor por falta de base, mas **não guarda** essas
recusas. São o sinal mais direto de "o que falta no acervo", e hoje ele se
perde. Trato isso como item separado na seção 9.

## 3. O desenho: o que ele é e o que ele não é

**O Agente 8 é um analista somente-leitura que produz achados com evidência,
para uma pessoa decidir.**

Ele **não é**:

- um agente que mexe em configuração — nem nas que ele mesmo sugere mudar;
- um agente que escreve, comita ou abre PR;
- um agente que lê o repositório (ver decisão **D1**, na seção 10);
- um agente que opina. Achado sem número não existe.

A arquitetura é a mesma do auditor da Fase 3, e por um motivo: ela já provou
que funciona. **Detectores determinísticos em Python**, cada um com janela e
amostra mínima declaradas, produzindo achados tipados. A IA entra depois e é
opcional — ver seção 8.

## 4. Os detectores do primeiro corte

Cada um é uma consulta sobre dado que **já existe**, com amostra mínima e
janela próprias. Os limiares moram no banco, não no código — como as regras do
auditor e os tetos de custo.

### Custo e modelo

| Chave | O que acha | Fonte |
|---|---|---|
| `MODEL_ERROR_RATE` | funcionalidade cujo modelo erra acima do limiar na janela | `ai_usage.status` |
| `MODEL_UNPRICED` | modelo usado no mês sem preço cadastrado — o total de custo está incompleto e ninguém é dono do conserto | `ai_usage` + `ai_models` |
| `CACHE_COLD` | funcionalidade com gasto alto e quase nenhum acerto de cache | `ai_usage.cached` |
| `ROUTE_INERT` | regra de roteamento ligada que **nunca se aplicou**, ou que fica sempre "não avaliada" porque a funcionalidade não declara o sinal de que ela depende | `ai_routing_decisions.trace` |
| `BUDGET_TREND` | gasto do mês projetado contra o teto, com os dias restantes | `ai_usage` + `ai_budgets` |

### Qualidade de conteúdo

| Chave | O que acha | Fonte |
|---|---|---|
| `SUSPECT_ANSWER_KEY` | questão com amostra suficiente e acerto **muito abaixo do acaso** — gabarito provavelmente errado | `question_attempts` |
| `AUDIT_RULE_INERT` | regra do auditor ligada que não achou nada na janela: ou o acervo está limpo, ou a regra está morta | `content_audits.findings` |
| `AUDIT_RULE_OVERRIDDEN` | regra que barra muito e é desligada ou contornada muito | `content_audits` + `audit_logs` |
| `NOT_CHECKED_CONCENTRATION` | regra que vive caindo em `NOT_CHECKED`: a conferência não consegue rodar | `content_audits.findings` |
| `ORPHANED_CONTENT_AGING` | conteúdo órfão por retificação, sem decisão humana há N dias | `notice_diffs` |

`SUSPECT_ANSWER_KEY` é, na minha avaliação, o detector mais valioso do agente
inteiro — e é pura estatística, sem IA. Uma questão de quatro alternativas que
3 em 100 candidatos acertam não é difícil: está com o gabarito trocado, e cada
dia que ela fica no ar ensina a coisa errada.

### Cobertura do edital

| Chave | O que acha | Fonte |
|---|---|---|
| `TOPIC_WITHOUT_LINK` | tópico do edital sem vínculo com o catálogo, ordenado pelo **peso na prova** | árvore de conhecimento |
| `TOPIC_WITHOUT_MATERIAL` | tópico vinculado e sem material, ordenado por peso × questões | árvore de conhecimento |

A Fase 7 já mostra essas duas lacunas na tela do candidato. O que o agente
acrescenta é a **ordem por custo de oportunidade**: a lacuna na disciplina de
peso 3 com 25 questões na prova não é igual à lacuna na de peso 1 com 5.

### Operação

| Chave | O que acha | Fonte |
|---|---|---|
| `AGENT_STEP_FAILING` | passo do orquestrador que falha repetidamente | `agent_steps` |
| `GENERATION_STALLED` | plano de geração confirmado que não avança | `generation_items` |

## 5. Os seis limites de segurança

Estes são a parte do desenho que peço para você aprovar explicitamente.

**L1 — Sem credencial de escrita em lugar nenhum.** O serviço escreve em uma
única tabela: a dos próprios achados. Nenhum detector chama API de
configuração, nem a do teto de custo, nem a das regras do auditor — nem para
aplicar o que ele mesmo propôs.

**L2 — Sem acesso ao repositório.** Nem leitura. Ver **D1**.

**L3 — Nenhum achado se aplica sozinho.** Todo achado nasce `OPEN` e espera
decisão humana. Mesmo os que teriam uma ação trivial pela API existente.

**L4 — Credencial de banco somente-leitura.** O desenho de código já restringe
a escrita a uma tabela, mas isso é disciplina, não garantia. A garantia é um
usuário de banco separado, com `SELECT` em tudo e `INSERT/UPDATE` apenas na
tabela de achados. Isso é item de infraestrutura e entra junto, não depois.

**L5 — Sem amostra, sem achado.** Cada detector declara janela e amostra
mínima. Abaixo disso ele reporta `NOT_ENOUGH_DATA` com o que falta — o mesmo
critério do `NOT_CHECKED` do auditor e do `NOT_EVALUATED` do roteador. Um
analista que opina sobre três chamadas de IA é pior que um analista calado.

**L6 — Economia só com número medido.** "Isto economizaria R$ X" só aparece
quando X sai de `ai_usage`, com a janela dita na frente. Sem custo medido, o
achado diz que não dá para estimar — e não estima.

## 6. O ciclo de vida de um achado

```
OPEN ──aceito──► ACCEPTED ──feito──► RESOLVED
  │
  └──recusado──► REJECTED (com motivo obrigatório)
```

Três regras no ciclo:

1. **Impressão digital.** Cada achado tem uma, derivada do detector + alvo. Uma
   nova passada **atualiza** o achado aberto em vez de criar o segundo igual. Um
   painel com o mesmo problema repetido 40 vezes é um painel que ninguém abre.
2. **Recusa é definitiva por um prazo declarado.** Achado recusado não volta
   pela mesma impressão digital durante N dias (configurável). Recusar e ser
   ignorado faria o administrador parar de recusar.
3. **`RESOLVED` é verificado, não declarado.** Quando o detector que gerou o
   achado deixa de achá-lo, ele fecha sozinho com essa constatação. Quando o
   administrador marca como feito mas o detector continua achando, o achado
   **reabre** dizendo isso. Fechar porque alguém disse que consertou é como
   acumular contador em vez de derivar estado.

## 7. Onde ele aparece

Uma aba no painel administrativo, ao lado do auditor: lista de achados por
severidade, com a evidência (os números e os registros que a produziram), a
ação proposta em texto e o destino — *administrador* (há tela para resolver) ou
*desenvolvimento* (precisa de código). Nenhum botão que aplique nada.

Execução: manual pelo painel, e como passo do orquestrador que já existe
(`AgentKey.IMPROVEMENTS`, hoje declarado e pulado com motivo). Nenhum
agendamento automático no primeiro corte — ligar a periodicidade antes de ver
o primeiro relatório é confiar em algo que ninguém leu ainda.

## 8. O papel do LLM: nenhum cálculo, só redação

A IA é **opcional e desligada por padrão**. Quando ligada, ela faz uma coisa
só: transformar o achado já calculado em um parágrafo legível com a sugestão
redigida. Ela não computa números, não decide severidade, não escolhe o que é
achado e não ordena a lista.

O texto dela é marcado como gerado por IA na tela, como todo texto de IA na
plataforma, e passa pelo mesmo teto de custo das outras funcionalidades
(entraria como `AIFeature.IMPROVEMENT_SUMMARY`, com modelo escolhido no painel
e sujeita ao roteador da Fase 6).

Com a IA desligada, o agente continua inteiro: o achado traz os números, a
regra violada e a ação proposta em texto de gabarito. A IA melhora a leitura,
não a conclusão.

## 9. O que fica fora do primeiro corte

- **Registro de recursos recusados.** Guardar `no_questions_available` e as
  recusas do tutor daria o melhor sinal de prioridade de acervo que a
  plataforma pode ter. É uma tabela de eventos nova e um detector a mais;
  proponho como parte 2, separado, para não misturar o agente com uma mudança
  de instrumentação.
- **Comparação entre períodos** ("o custo por aula caiu depois da Fase 6"). Útil
  e fácil de errar; depende de o roteador ter histórico suficiente.
- **Qualquer sugestão sobre o candidato individual.** O agente analisa a
  plataforma, não pessoas. Sugestão de estudo é o tutor, e ele já existe.
- **Agendamento automático** — ver seção 7.

## 10. As três decisões que são suas

### D1 — O agente propõe código, ou só descreve a mudança?

No plano original eu escrevi que a saída dele seria *"texto e diff em anexo"*.
**Mudei de opinião e explico:** produzir um diff exige (a) acesso de leitura ao
repositório e (b) um modelo escrevendo código. Isso multiplica a superfície de
risco para entregar um patch que ninguém executou e que um revisor vai ter que
conferir linha por linha de qualquer forma — e um patch plausível e errado é
mais perigoso que uma descrição precisa, porque convida a aplicar sem ler.

| Opção | O que muda |
|---|---|
| **A (recomendada)** | sem acesso ao repositório; o achado descreve a mudança em texto e aponta o módulo quando o detector sabe qual é |
| **B** | leitura do repositório + modelo escrevendo o patch; nunca aplicado, nunca empurrado, sempre anexo |

Se você escolher **B**, peço que seja numa segunda etapa, depois de o primeiro
relatório da opção A existir e você ter lido.

### D2 — A credencial somente-leitura de banco (L4) entra junto?

Ela exige mexer no `docker-compose` de produção e no `.env` da VPS para criar
um segundo usuário MySQL. É o que transforma "o código não escreve" em "o banco
não deixa escrever". Recomendo que entre junto; se preferir adiar, o agente
sai com a restrição apenas no código, e isso fica dito no painel.

### D3 — Quais detectores entram no primeiro corte?

Os treze da seção 4 são todos construíveis sobre dado existente. Se preferir
um corte menor para ver o formato antes, sugiro estes quatro, que dão o maior
retorno por esforço:

1. `SUSPECT_ANSWER_KEY` — conserta conteúdo errado no ar;
2. `TOPIC_WITHOUT_MATERIAL` — diz onde gerar primeiro, por peso na prova;
3. `MODEL_ERROR_RATE` — pega provedor quebrado antes do usuário reclamar;
4. `ROUTE_INERT` — pega regra de roteamento que não faz nada.

## 11. O que eu não vou fazer sem a sua resposta

Nada. Este documento não tem código, tabela, migração nem rota. O
`AgentKey.IMPROVEMENTS` continua declarado e **pulado com motivo escrito** no
orquestrador, como está desde a Fase 2, até você aprovar o desenho e as três
decisões acima.

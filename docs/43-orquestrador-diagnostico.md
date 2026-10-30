# Fluxo de agentes: o que estava quebrado, e o que foi corrigido

> Relato recebido sobre o concurso *TJSP 2026 — Escrevente Técnico Judiciário*:
> oito observações, do "Analista de editais pulado" ao "Auditor falhou após duas
> tentativas sem causa" e às expirações de sessão no meio do cadastro.

Duas das observações **não eram defeito** e estão respondidas abaixo com a
evidência. As outras seis eram, e três delas tinham a mesma raiz: o orquestrador
usava um estado só — `SKIPPED` — para três coisas que pedem ações opostas.

## 1. Causas encontradas

### 1.1 Falta de insumo consumia tentativa (observações 1 e 5)

`_run_step` incrementava `attempts` **antes** de chamar o agente e mantinha o
incremento quando o resultado era "não havia o que fazer". O Analista de
editais, sem PDF, devolvia `skipped=True` — e gastava uma tentativa. Duas
execuções depois, `attempts == max_attempts`.

```python
# antes
step.attempts += 1
outcome = await runner(...)        # devolve skipped=True: faltou o PDF
step.status = SKIPPED if outcome.skipped else DONE   # a tentativa fica gasta
```

Nenhuma repetição faz um PDF aparecer. Era o pior lugar possível para gastar
tentativa, porque o efeito aparecia num agente diferente do que tinha o
problema.

### 1.2 A mensagem de "esgotou as tentativas" apagava a causa (observação 5)

```python
# antes
if not can_retry(spec, step.attempts):
    step.status = StepStatus.FAILED
    step.detail = f"Esgotou as {spec.max_attempts} tentativas."   # <- apagou
```

`step.detail` era o **único** lugar onde a causa da falha vivia. A terceira
chamada ao passo substituía o diagnóstico pela contagem. Isto explica
literalmente o que o painel mostrava do Auditor: *"Esgotou as 2 tentativas"*, e
nada mais. A causa original não estava escondida — tinha sido sobrescrita.

### 1.3 Erro de banco dentro de um agente derrubava o tratamento de erro

O `except` registrava a falha e seguia usando a **mesma sessão**:

```python
except Exception as exc:
    step.detail = str(exc)[:1000]
gasto_depois = (await self.budget.overview()).spent_month_cents   # SELECT
await self.session.commit()
```

Um erro de banco deixa a transação morta: todo `SELECT` seguinte estoura com
`PendingRollbackError`. O `overview()` logo abaixo quebrava, a exceção subia
por cima da original, e o que chegava ao painel era um erro de infraestrutura
no lugar da causa. Para o Auditor, cuja varredura faz muitas consultas, este é
o caminho mais provável da falha relatada — e ele é agora reproduzido em teste
(`test_a_database_error_inside_an_agent_does_not_break_the_orchestrator`).

### 1.4 Grafo de dependências travava aula e tutoria em amostra estatística (2 e 3)

`TEACHER` e `TUTOR` dependiam de `STATISTICS`. Sem prova anterior da banca, a
estatística não roda; e como só `DONE` satisfazia dependência, Professor e Tutor
eram pulados em cascata. Mas a incidência **ordena** o que estudar primeiro —
ela não autoriza um tópico do edital a existir. Aula sobre tópico confirmado não
depende de amostra nenhuma.

### 1.5 A auditoria registrava SUCCESS para execução falhada (observação 7)

`AuditService.record` tem `status: str = "SUCCESS"` por padrão — um padrão que
descreve **a requisição**. O orquestrador chamava `record(AGENT_RUN_FINISHED)`
sem passar status, então toda execução terminava auditada como sucesso,
inclusive as que falharam. Os quatro níveis que o pedido separa (requisição,
aceite do job, resultado do passo, resultado da execução) estavam colapsados num
só.

### 1.6 Renovação de token apresentava o mesmo refresh token duas vezes (8)

O servidor **rotaciona** o refresh token e **detecta reuso**: reapresentar um
token já rotacionado revoga a família de sessões inteira
(`revoke_family(..., "REUSE_DETECTED")`). É a decisão de segurança correta, e
nada foi afrouxado nela.

O defeito era do cliente. A fila de renovação era uma variável de módulo — por
**aba**:

```js
let refreshPromise = null   // vive na aba; localStorage é compartilhado
```

Duas abas expirando juntas leem o mesmo `localStorage`, apresentam o mesmo
token, e o servidor — corretamente — mata a família. O usuário vê "sessão
expirada" no meio do trabalho.

E havia um segundo: o `catch` da renovação devolvia `null`, e quem chamava
tratava `null` como "o servidor recusou" e limpava os tokens. **Uma oscilação de
rede derrubava a sessão.**

### 1.7 Execução rodava dentro da requisição HTTP

Não havia tarefa de fila para o orquestrador: `POST /run` executava os oito
agentes inline. Fechar a aba, expirar a sessão ou o proxy cortar a conexão
cancelava a tarefa no meio, e os passos ficavam `RUNNING` para sempre — sem
marca de tempo, não havia como saber que o processo tinha morrido.

### 1.8 `run.error` era lido pela API e nunca escrito

`agents.py` serializava `error=run.error`; nada no orquestrador atribuía esse
campo. O painel recebia `null` mesmo numa execução falhada.

## 2. O que **não** era defeito

### Memorização e Mestre de batalhas (observação 4)

Os dois **estão implementados** desde os commits `e4d089b` e `77cd791`, e
registrados em `register_default_agents()`. O relato é anterior a eles. Há teste
cobrando que catálogo e registro contem a mesma história
(`test_the_eight_agents_of_the_request_all_have_a_runner`).

### Cinco detectores sem amostra (observação 6)

É o comportamento desenhado, não falha. Cada detector devolve
`NOT_ENOUGH_DATA` com o que faltou, e o painel mostra "sem amostra para rodar"
com cor própria, distinta de "conferiu e não achou". O que **mudou** aqui é mais
honesto ainda: o passo agora termina `DONE_WITH_NOTES` em vez de `DONE`, e cada
detector que não rodou aparece nomeado na lista de ressalvas. Falta de amostra
nunca passa por ausência comprovada de problema.

## 3. Correções implementadas

### A máquina de estados

`SKIPPED` fazia o trabalho de três estados. Agora:

| Estado | Pergunta que responde | Consome tentativa? |
|---|---|---|
| `PENDING` | aguardando execução | — |
| `RUNNING` | executando | sim (já contada) |
| `DONE` | cumpriu o contrato | sim |
| `DONE_WITH_NOTES` | cumpriu, com ressalvas declaradas | sim |
| `SKIPPED` | rodou e não havia o que fazer | sim |
| `AWAITING_INPUT` | falta PDF, provedor, amostra, candidato | **não** |
| `BLOCKED` | dependência não cumpriu o contrato | **não** |
| `NOT_IMPLEMENTED` | declarado sem implementação registrada | **não** |
| `FAILED` | quebrou | sim |
| `BUDGET_BLOCKED` | barrado pelo teto | **não** |
| `CANCELED` | interrompido por decisão de alguém | **não** |

Só `DONE` e `DONE_WITH_NOTES` satisfazem dependência: "não havia o que fazer" é
resultado honesto do passo, mas não entrega o insumo que o próximo esperava.

Na execução inteira, `BUDGET_BLOCKED` deixou de significar `FAILED` — teto de
gasto é a regra funcionando, e chamar isso de falha mandava alguém procurar um
defeito inexistente. Entrou `DONE_WITH_NOTES`: tudo que podia rodar rodou, e
sobrou coisa esperando uma pessoa.

### O diagnóstico

- **A causa não é mais sobrescrita.** "Esgotou as tentativas" virou propriedade
  derivada (`attempts_exhausted`), exibida **ao lado** da causa.
- **Histórico por tentativa** (`agent_step_attempts`): número, estado, causa,
  código de erro estável, classe da exceção, pilha, id de correlação, duração e
  custo. A pilha fica no servidor; o painel recebe a causa em português.
- **Rollback antes de registrar a falha**, e o ator é recarregado depois — o
  rollback expira todos os objetos da sessão, e auditar com objeto expirado
  disparava um SELECT fora do laço assíncrono.
- **`_explain(exc)`** traduz a exceção: `AppError` entrega mensagem e código;
  exceção sem mensagem deixa de virar string vazia (indistinguível de "não sei").
- **O motivo do bloqueio traz o que houve com a dependência**: *"Depende de
  Analista de editais (aguardando insumo: o edital está cadastrado, mas sem
  arquivo PDF enviado)"* — resolvido na primeira leitura, sem caçar o outro passo.

### A auditoria, em quatro níveis

| Nível | Onde aparece |
|---|---|
| Requisição HTTP | código de status da resposta |
| Aceite do job | `AGENT_RUN_STARTED` com status `ACCEPTED` |
| Resultado do passo | `AGENT_STEP_RUN` com `SUCCESS`/`PARTIAL`/`PENDING_INPUT`/`BLOCKED`/`FAILED`/… |
| Resultado da execução | `AGENT_RUN_FINISHED` com `SUCCESS`/`PARTIAL`/`FAILED`/`CANCELED` |

A meta de cada registro leva a contagem de passos por estado, o custo e o id de
correlação.

### Execução durável

`agents.run_all` (Celery) executa fora do ciclo HTTP; `POST /run` aceita o job e
devolve na hora. Sem broker (desenvolvimento e teste) roda inline, como a
análise de edital já fazia — enfileirar para uma fila que não existe seria
aceitar trabalho que nunca sairia. Fila indisponível em produção cai para a
execução inline em vez de perder o pedido.

- **Idempotência**: a trava é `UPDATE … WHERE status <> 'RUNNING'`, no banco.
  Ler e depois escrever deixava dois pedidos simultâneos passarem os dois.
- **Retomada**: passo em estado terminal é deixado quieto, então reiniciar o
  worker não refaz o que já custou IA.
- **Passo travado**: `heartbeat_at` + `agents.recover_stuck` devolvem ao fluxo o
  passo cujo processo morreu, com o motivo escrito.
- **Cancelamento**: estado próprio, preservando o que já terminou.

### Pré-requisitos

`GET /admin/agents/{id}/preflight` responde o que falta **antes** de disparar
oito agentes: edital, PDF, banca, modelo vinculado e teto de gasto — cada um com
a ação que resolve (`ATTACH_PDF`, `CONFIGURE_AI`, `RAISE_BUDGET`…). Não chama IA
e não escreve nada.

### Autenticação

Sem afrouxar nada no servidor: a rotação e a detecção de reuso continuam como
estavam.

1. **A fila de renovação atravessa abas**, por um registro em `localStorage` com
   prazo de 10 s. Duas abas não apresentam mais o mesmo token.
2. **Token que outra aba acabou de renovar é reaproveitado**: depois de esperar
   a fila, o cliente relê o armazenamento; se o access token mudou, ele serve, e
   não há segunda renovação para gerar reuso.
3. **Falha de rede deixou de ser sessão inválida.** `unreachable` e `rejected`
   são resultados diferentes: só o segundo limpa os tokens. O formulário em
   andamento sobrevive a uma oscilação.
4. **Fila abandonada expira**, para aba fechada no meio não travar a renovação
   para sempre.

## 4. Migrações e configuração

| Item | Detalhe |
|---|---|
| `79d115df3527` | `agent_step_attempts` (histórico), `agent_steps.heartbeat_at`, `agent_runs.request_id`/`canceled_at`/`canceled_by_user_id` |
| Fila | `app.workers.tasks.agents` registrado em `celery_app`; nada a configurar além do broker que já existe |
| `agents.recover_stuck` | convém agendar no Celery beat; sem agendamento, ela roda no começo de cada execução pela fila |

Nenhuma configuração nova de ambiente. Nenhum dado existente é alterado: as
colunas novas são anuláveis e o histórico começa vazio.

## 5. O que ficou de fora

- **Nada foi executado contra dados de produção**, e nenhum conteúdo foi
  publicado. O diagnóstico do Auditor em TJSP2607 é a causa **provável** —
  reproduzida em teste —, não a leitura do registro de produção daquele
  concurso: não tenho acesso a ele, e o histórico por tentativa só passa a
  existir a partir desta mudança. Para confirmar a causa original naquele caso
  específico, basta reexecutar o passo depois do deploy: a causa agora fica
  gravada.
- **A rotina de varredura de travados não foi agendada** no beat; a tarefa
  existe e é chamada no início de cada execução pela fila.
- **O custo por passo continua sendo a diferença do gasto no período.** Se duas
  execuções correrem juntas, o custo pode ser atribuído à errada. Medir por
  chamada exigiria carimbar cada linha de `ai_usage` com o passo — vale, e não
  está feito.
- **OCR**: o projeto extrai texto por página com PyMuPDF e **não tem OCR**.
  Edital publicado como imagem continua sem texto aproveitável, e a análise
  recusa com `empty_extraction` em vez de inventar. É limitação declarada, não
  corrigida aqui.

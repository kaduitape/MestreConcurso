# Fase 6 — roteador de modelos (e o que ficou de fora)

> Item 14 do plano em [27-evolucao-agentes-diagnostico.md](27-evolucao-agentes-diagnostico.md):
> *"roteador configurável e auditável"*. O item 15 — o adaptador do JEV —
> **continua bloqueado**, pelo mesmo motivo de antes. A seção final explica.

## O problema

Até aqui, a resposta para "qual modelo atende esta chamada?" era uma só: o que
o administrador vinculou à funcionalidade no painel (`ai_feature_bindings`).
Isso basta enquanto todas as chamadas de uma funcionalidade são parecidas, e
deixa de bastar quando não são — analisar um edital de 8 páginas e um de 300 é
a mesma funcionalidade e não é o mesmo trabalho.

O critério de aceite da fase é estreito e verificável:

> **F6:** a escolha de modelo é auditável — dá para dizer por que aquele modelo
> foi usado naquela execução.

Note o que ele **não** pede: nem economia, nem escolha "inteligente". Pede
explicação. Um roteador que escolhe bem e não registra nada troca um
comportamento previsível (um modelo por funcionalidade) por um que ninguém
consegue explicar depois.

## As três regras do desenho

### 1. A decisão é determinística — nenhuma IA escolhe o modelo

`app/domain/model_routing.py` é uma função pura: entram sinais medidos e regras
cadastradas, sai a decisão. A mesma entrada dá sempre a mesma saída.

Houve a tentação de pedir a um modelo barato para julgar a complexidade da
pergunta e escolher o modelo caro só quando valesse a pena. Isso trocaria uma
pergunta auditável por um palpite — e um palpite pago, já que a avaliação
também é uma chamada. A regra do projeto contra deixar o LLM responsável por
cálculo vale aqui: a decisão de gasto é um cálculo.

### 2. Sinal ausente não vale como falso

Os sinais são três, e só entram na lista porque a plataforma os **mede**:

| Sinal | De onde vem |
|---|---|
| `INPUT_CHARS` | tamanho do texto que vai na requisição, contado por quem monta o prompt |
| `NEEDS_JSON` | a chamada exige resposta em JSON |
| `BUDGET_USED_PCT` | gasto do mês ÷ teto mensal cadastrado |

Quem chama declara o que sabe. O que não sabe fica em branco — e a regra que
dependia daquilo fica **`NOT_EVALUATED`**, dizendo qual sinal faltou.

Tratar ausência como zero faria a condição "entrada acima de 50 mil
caracteres" parecer respondida quando ninguém mediu nada. O mesmo vale para o
orçamento: **sem teto mensal cadastrado não existe percentual do teto**, então
`budget_used_pct` devolve `None`, não `0`.

Seis chamadas de IA declaram sinais hoje: análise de edital, tutor,
classificação de questão, roteiro do Estúdio, mapa mental e geração de
flashcards. As demais não declaram nada e continuam recebendo o modelo
vinculado — com a decisão registrada dizendo exatamente isso.

### 3. Toda escolha carrega o rastro inteiro

Todas as regras são avaliadas, inclusive as que vêm depois da vencedora. Custa
algumas comparações e evita um histórico cheio de "não cheguei a olhar" — que
não responde por que as outras não venceram.

Cada resolução grava uma linha em `ai_routing_decisions` com o motivo
(`BINDING_DEFAULT`, `RULE_MATCHED`, `FALLBACK_AFTER_ERROR`), a explicação em
texto, os sinais realmente informados e o resultado de cada regra. E cada linha
de `ai_usage` passa a apontar para a decisão que escolheu aquele modelo
(`routing_decision_id`): é isso que transforma "por que este modelo?" de
aproximação de horário entre duas tabelas em consulta direta.

Como em `record_usage`, a decisão é gravada em **sessão própria** — precisa
sobreviver ao erro de quem chamou, porque a chamada de IA aconteceu de
qualquer forma.

## As regras não moram no código

`ai_model_routes` guarda uma linha por regra: funcionalidade, rótulo,
prioridade, modelo de destino e as condições em colunas próprias
(`min_input_chars`, `max_input_chars`, `requires_json`,
`min_budget_used_pct`). Mudar "edital acima de 80 mil caracteres usa o modelo
grande" é um `UPDATE`, não um deploy.

As condições são colunas, e não um JSON de expressão, de propósito: uma
condição que o banco sabe ler é uma condição que a tela sabe mostrar e o teste
sabe conferir. Uma linguagem de expressão guardada em texto seria uma caixa
preta com um passo a mais.

Todas as condições preenchidas precisam valer ao mesmo tempo. Condição em
branco não condiciona. Regra sem nenhuma condição vale para toda chamada da
funcionalidade — e o rastro escreve isso, em vez de deixar a pessoa deduzir.

A primeira regra que atende, na ordem de prioridade, vence. O teto é de 20
regras por funcionalidade: não é limite de produto, é o que mantém o rastro
legível numa tela.

## Duas funcionalidades recusam roteamento

Esta é a parte do desenho que nasceu de um risco real que o roteador cria.

**Embedding não pode ser roteado.** Um vetor gerado por outro modelo vive em
outro espaço. A busca semântica compararia os vetores novos com os já
indexados como se fossem comparáveis, e devolveria trechos errados com a mesma
cara de certos. O cadastro recusa a regra, com esse motivo escrito.

**A narração não pode ser roteada.** O áudio de uma aula é gerado cena por
cena; um modelo diferente entre cenas trocaria a voz do narrador no meio da
aula.

O painel não oferece essas duas funcionalidades no formulário, e a API recusa
com `ai_route_feature_not_routable` se alguém tentar pela porta de trás.

## O modelo de reserva — uma coluna morta que passou a existir

`ai_feature_bindings.fallback_model_id` existe desde a Fase 2 e **nunca foi
lida por ninguém**: um campo no banco sem comportamento, exatamente o tipo de
coisa que o projeto proíbe. Agora ela tem comportamento, em
`app/ai/fallback.py`:

- **Só erro passageiro aciona a reserva** — limite de requisições
  (`429`) e provedor fora do ar (`503`). Chave inválida **não**: cair na
  reserva ali esconderia uma configuração errada que alguém precisa consertar.
- **Uma tentativa, não uma cadeia.** A reserva da reserva não existe.
- **Cada chamada é medida separadamente.** A falha vai para `ai_usage` com
  `status=ERROR`; o acerto vai com `SUCCESS` e uma decisão própria marcada
  `FALLBACK_AFTER_ERROR`. Somar as duas sob um registro só esconderia a
  primeira, que consumiu tempo e pode ter consumido token.
- **Embedding e narração não têm reserva**, pelos mesmos motivos da seção
  anterior.

A decisão do desvio é gravada **no momento em que ele acontece**, não antes:
registrar um desvio que talvez não ocorra seria afirmar o que não houve.

## Um defeito encontrado no caminho

`set_binding` gravava `binding.model_id` em vez de `binding.model`. Como a
fábrica de sessões usa `expire_on_commit=False`, um vínculo que já estava
carregado na memória mantinha o relacionamento antigo depois do commit — e a
resposta da API saía dizendo que não havia reserva logo depois de gravar uma.
A correção foi atribuir o relacionamento, e não só a coluna da chave
estrangeira. O mesmo valia, de forma latente, para a troca do modelo principal.

Também saiu do caminho uma escrita escondida: ler a pressão do orçamento
passava por `AIBudgetService._row()`, que **insere** a linha de configuração
quando ela não existe. Resolver qual modelo usar não pode escrever no banco —
além do efeito colateral escondido, no SQLite dos testes isso travava a
transação de quem só queria decidir. `month_spend_and_limit()` lê sem criar
nada.

## O que o JEV faria aqui, e por que ele continua fora

O desenho original previa o JEV (TypeSafe AI) como a peça que escolheria a
faixa de modelo por complexidade — uma pergunta tipada `choice` com
probabilidade calibrada. Esse ainda é o lugar certo para ele, e o roteador
está pronto para recebê-lo: a decisão já é uma função pura sobre sinais, e um
sinal novo vindo de um `DecisionProvider` entraria sem reescrever nada.

Mas a documentação oficial (`docs.typesafe.ai/api`) **continua inacessível
deste contêiner** — DNS bloqueado pela política de rede do ambiente;
verificado de novo nesta fase. As fontes de terceiros divergem em detalhes do
protocolo (o tipo da pergunta sim/não aparece como `boolean` em umas e `noul`
em outras; o caminho `/v1/evaluate` não está confirmado).

Escrever o adaptador com o protocolo adivinhado é exatamente a integração
inventada que o pedido proíbe. Continua valendo o que ficou combinado: preciso
da referência da API colada aqui, ou do domínio liberado na política de rede,
ou de uma chamada de exemplo que funcione na sua conta.

**Não há nenhum arquivo, porta ou botão de JEV no código.** Uma porta
`DecisionProvider` sem implementação seria uma abstração morta — a mesma coisa
que a coluna `fallback_model_id` era antes desta fase.

## Como conferir

```bash
# Domínio: a decisão e o rastro
pytest tests/unit/test_model_routing_domain.py -q

# Ponta a ponta: a regra valendo, a reserva, o vínculo com o gasto
pytest tests/integration/test_model_router.py -q
```

No painel, em **IA → Roteador de modelos**: cadastre uma regra, dispare uma
classificação de questão e abra *Por que cada modelo foi usado*.

### O que foi verificado

| Verificação | Resultado |
|---|---|
| Migração `8b9f371ddc04` em SQLite | up / down / up, `alembic check` limpo |
| Migração em MySQL 8.4 real | up / down / up, carimbo em `(head)` |
| Backend | suíte completa verde |
| Frontend | 285 testes, ESLint, `tsc --noEmit` e build limpos |

## Crescimento das tabelas

`ai_routing_decisions` ganha uma linha por chamada de IA — mesma ordem de
grandeza de `ai_usage`, que também não é expurgada. Nenhuma das duas tem rotina
de limpeza hoje, e isso é uma escolha consciente: são o histórico que responde
"quanto custou e por quê". Se o volume incomodar, o expurgo entra como tarefa
de manutenção com retenção configurável no banco — não como constante no
código.

## O que esta fase não entrega

- **Adaptador do JEV** (item 15) — estava bloqueado, como explicado acima.
  **Resolvido na [parte 2c](41-fase4-parte2c-jev-julgamento-tipado.md)**, com a
  documentação em mãos: o JEV entrou como provedor de **julgamento tipado**, em
  porta paralela à de texto, e não como roteador — a premissa original do pedido
  estava errada, e a advertência deste documento se confirmou inteira.
- **Escolha automática de modelo por complexidade** — não existe medida de
  complexidade que não seja palpite. Entraria se o JEV entrar.
- **Reserva para embedding e narração** — recusada por desenho, não esquecida.
- **Rotear por usuário ou por plano** — nenhum sinal de plano é informado às
  chamadas hoje; inventar um seria roteamento sobre dado que não existe.

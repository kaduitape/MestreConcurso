# Fase 4 (parte 2a) — O baralho oficial por tópico

> Segue a [parte 1](32-fase4-geracao-em-massa.md), que entregou a geração em
> massa de aula e mapa mental e deixou dois agentes declarados e pulados. Esta
> parte constrói o que faltava para o **agente de memorização**: o baralho
> oficial. A geração de questões (agente *mestre de batalhas*) continua fora, e
> a razão está no fim deste documento.

## As duas decisões que estavam abertas

Esta parte dependia de duas decisões de produto que eu havia perguntado três
vezes sem resposta. Em vez de perguntar uma quarta, eu as **derivei do que o
próprio projeto já decidiu em casos iguais**, e as deixo escritas aqui para
serem contestadas:

1. **O baralho oficial entra de forma aditiva.** O cartão do candidato não
   muda, não é migrado e não é substituído. O baralho oficial é uma camada
   nova, ligada ao tópico canônico — exatamente o precedente da Fase 1, que
   ligou conteúdo ao catálogo sem reescrever nada, e o do mapa mental, que se
   liga ao tópico e não ao concurso.
2. **Cartão gerado por IA nasce rascunho e espera uma pessoa.** É o mesmo
   caminho da aula e do mapa na parte 1: a IA produz, o portão da Fase 3
   confere, e **quem publica é gente**. Para o cartão há uma exigência extra
   que já existia no baralho pessoal: a citação precisa aparecer **literalmente**
   no material, ou o cartão é descartado.

Se alguma das duas estiver errada, o que muda é pequeno e localizado: a
primeira vive em `app/models/deck.py` e na visibilidade do repositório; a
segunda, no portão de publicação.

## Diagnóstico: metade disto já existia

A primeira surpresa foi que o motivo escrito na ficha do agente estava
**parcialmente errado**. Ele dizia que "não há onde guardar um baralho oficial
por tópico". Na verdade havia:

3. `flashcards.user_id` já era **nulo-permitido**, com o comentário "nulo
   significa cartão global, disponível para todos".
4. Cartão e **estado de memória** já eram tabelas separadas, e o docstring do
   modelo dizia por quê: *"um cartão global (curado pela equipe) é revisado por
   muita gente, e cada pessoa tem seu próprio intervalo"*.
5. `CardOrigin` já tinha `EDITORIAL` (curadoria da equipe) e `AI`.
6. O repositório já somava os cartões globais aos do candidato.

O que faltava não era onde guardar o **cartão** — era onde guardar o
**baralho**, e com ele três coisas que só o baralho resolve:

- **Escopo.** Com a visibilidade antiga, qualquer cartão global entraria na fila
  de **todo mundo**. Um baralho de "Controle de Constitucionalidade" cairia na
  revisão de quem estuda para um concurso de saúde municipal. Nada disso
  aconteceu em produção porque nenhum caminho do código criava cartão global —
  mas a porta estava aberta, e esta parte a fecha.
- **Portão de conferência.** Sem um estado de publicação, cartão gerado por IA
  chegaria a candidato no instante em que fosse gravado.
- **Reaproveitamento.** O plano de geração decide "gerar ou reaproveitar" por
  tópico. Sem a entidade baralho não havia o que reaproveitar.

## O desenho

### Duas tabelas e uma coluna

7. `official_decks` — um baralho por tópico (`topic_id` **único**: "o baralho
   oficial do tópico" não pode ser ambíguo, nem para o candidato nem para o
   plano de geração). Guarda estado (`DRAFT`/`PUBLISHED`/`ARCHIVED`), a
   procedência (`EDITORIAL`, `LESSON`, `NOTICE`, `MATERIAL`), quem criou e
   **quem publicou**, com data.
8. `official_deck_subscriptions` — o candidato escolheu receber aquele baralho.
   É consentimento, não progresso.
9. `flashcards.deck_id` — cartão sem dono **e** sem baralho deixa de existir
   como conceito: seria conteúdo entrando na fila de alguém sem ninguém ter
   escolhido.

### Três portas, nenhuma opcional

10. O cartão oficial chega a um candidato quando, e só quando: o baralho foi
    **publicado** por uma pessoa **e** o candidato **assinou** o baralho **e** o
    cartão está **ativo**. O teste
    `test_an_official_card_reaches_only_who_entered_a_published_deck` passa
    pelas três portas, uma a uma, conferindo que cada fechada basta para o
    cartão não aparecer.
11. A visibilidade virou uma função só, em `app/repositories/flashcard.py`, e
    passou a valer **também para a fila de revisão**. Antes, listagem e fila
    usavam critérios diferentes — e isso já era um defeito: cartão desativado
    continuava na fila de quem já o tinha, porque o estado de memória não era
    filtrado por visibilidade. Agora é.

### Sair não apaga memória

12. Cancelar a assinatura tira os cartões da fila e **não apaga** o estado de
    memória de ninguém. Quem volta meses depois reencontra os intervalos onde
    parou.
13. O mesmo vale para a curadoria: tirar um cartão de circulação e arquivar um
    baralho retiram conteúdo da fila sem destruir histórico de revisão. São
    coisas diferentes, e a interface diz isso em palavras.

## O agente de memorização

14. Ele executa os planos de geração **já confirmados por uma pessoa**, no tipo
    `FLASHCARD_DECK`. Não confirma plano, igual ao Professor: quem autoriza o
    gasto é gente.
15. O insumo é **aula publicada**. Uma aula em rascunho é, por definição, o que
    ainda não passou por conferência humana — gerar cartão dela seria
    contrabandear texto de IA não revisado para a repetição espaçada de quem
    estuda, que é o lugar onde um erro é gravado com mais força.
16. Tópico sem aula publicada não vira falha: o item fica `NO_SOURCE`, um estado
    novo com o motivo escrito — *"o cartão oficial não nasce de rascunho"*. Nem
    um token é gasto nesse caminho, e o teste confere isso.
17. O baralho produzido fica **em rascunho**. O detalhe do passo termina em
    "Nenhum baralho foi publicado: rascunho espera conferência humana".

### A fronteira entre Professor e Memorização

18. Os dois agentes dividem o mesmo plano, e a passada passou a aceitar um
    filtro por tipo. Sem ele, o primeiro a rodar levaria o crédito pelo
    trabalho do outro na tela de acompanhamento — e a tela mentiria sobre quem
    fez o quê. Há um teste exatamente para isso.
19. No caminho, o `if/else` de dois tipos virou despacho explícito. Com um
    terceiro tipo, o `else` silencioso geraria **mapa mental** para um item de
    baralho, e nenhum teste de aula ou de mapa pegaria isso.

## O portão da Fase 3 passou a conhecer baralho

20. `FLASHCARD_DECK` é um novo tipo de alvo da auditoria de conteúdo. Herda as
    regras gerais — tópico fora do edital, conteúdo sem vínculo, **IA sem
    conferência humana** — e a de corpo vazio, com a mensagem no vocabulário
    certo: *"baralho sem cartão ativo não vai para quem estuda"*.
21. Publicar passa pelo portão **antes** de mudar o estado: baralho barrado não
    fica publicado nem por um instante, e o laudo é gravado mesmo quando a
    publicação é recusada.
22. O baralho se liga ao tópico, não ao concurso. Então "tópico fora do edital"
    sai como **não verificada** em vez de inventar um edital de referência —
    a mesma escolha feita para o mapa mental.

## O que a interface mostra

23. **"Oficial" e "gerado por IA" são dois selos diferentes**, e os dois
    aparecem juntos quando é o caso. Oficial diz quem publicou; gerado por IA
    diz quem escreveu. Um cartão oficial de IA continua declarado como de IA
    depois de publicado — na listagem e na tela de revisão.
24. Na curadoria, o rascunho diz *"rascunho — ninguém vê"*, e o que a geração
    **descartou** por falta de citação literal aparece na tela, com os
    enunciados. Esconder o descarte faria a geração parecer melhor do que foi.
25. No catálogo do candidato, a lista diz **de onde vem**: os baralhos dos
    tópicos do edital do concurso principal dele. Sem concurso principal
    escolhido, ela mostra só o que ele já assinou e diz isso — despejar todo
    baralho publicado da plataforma seria fingir recomendação.
26. Entrar e sair do baralho são ações do candidato. Nenhum baralho aparece na
    fila por decisão da plataforma, e nada aqui fica atrás de nível, liga ou
    plano pago.

## Permissões

27. Duas permissões novas: `decks:read` e `decks:write`. A equipe
    (papel *staff*) recebe as duas, como já recebia as do estúdio: curadoria de
    conteúdo é trabalho dela, e publicar passa pelo portão de todo jeito. O
    seed de RBAC é idempotente, então elas entram no deploy sem passo manual.

## Como conferir

```bash
# Escopo: publicar não é entregar
pytest tests/integration/test_decks.py -q

# O agente: rascunho não vira cartão; aula publicada vira baralho em rascunho
pytest tests/integration/test_agent_memory.py -q

# O tipo novo no plano e o estado NO_SOURCE
pytest tests/unit/test_generation_domain.py -q -k "kind or material"

# O portão conhecendo baralho
pytest tests/unit/test_content_audit_domain.py -q -k deck
```

No painel: **Administração → Estúdio → Baralhos oficiais**. Para quem estuda:
**Baralhos oficiais**, no menu de treinamento.

### O que foi verificado

| Verificação | Resultado |
|---|---|
| Migração `c4a1f2e97d3b` em SQLite | up / down / up, `alembic check` limpo |
| Migração em MySQL 8.4 real | up / down / up, carimbo em `(head)` |
| Defeito de ordem no `downgrade` | encontrado e corrigido (ver abaixo) |
| Backend | suíte completa verde |
| `ruff check` / `ruff format` | limpos |
| `mypy` nos arquivos desta parte | limpo |
| Frontend | `npm run lint`, `npm run typecheck` e `vitest` verdes |

## Um defeito que só o MySQL mostrou

28. O `downgrade` soltava os índices de `flashcards.deck_id` antes da chave
    estrangeira. No SQLite isso passa; no MySQL, não: ele exige um índice que
    comece pela coluna da chave estrangeira e recusa soltá-lo enquanto ela
    existe (`ERROR 1553`).
29. O efeito era pior do que uma mensagem de erro: o primeiro índice saía, o
    segundo era recusado, a migração abortava no meio — e a tabela
    `alembic_version` continuava carimbada como aplicada. O banco ficava com a
    migração meio desfeita e se declarando em dia.
30. A ordem foi invertida: a chave sai primeiro, depois os índices, depois a
    coluna. A verificação agora é up / down / up em MySQL 8.4 real, não só em
    SQLite — que é exatamente o tipo de diferença que o SQLite dos testes não
    pega.

## O que esta parte não entrega

- **Geração de questões (agente *mestre de batalhas*).** É a parte 2b: a
  plataforma classifica questão por IA, mas não gera, e gerar exige validação
  de gabarito na origem. O agente continua declarado e pulado, agora com o
  motivo real na ficha dele.
- **Baralho a partir de trecho de edital.** A procedência `NOTICE` existe no
  modelo porque o cartão do baralho pessoal já nasce de edital, mas nenhum
  caminho automático a usa ainda.
- **Recomendação de baralho.** O catálogo lista o que o edital do candidato
  cobre, em ordem alfabética. Ordenar por prioridade de estudo é trabalho do
  tutor, e misturar as duas coisas agora esconderia de onde vem a ordem.
- **Edição de cartão oficial depois de publicado.** Hoje a curadoria tira de
  circulação e escreve outro. Editar um cartão que já está na memória de
  centenas de pessoas é uma decisão com consequência — a frente muda, o estado
  de memória continua —, e ela merece desenho próprio.

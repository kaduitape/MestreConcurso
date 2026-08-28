# Critérios de Aceite — Gamificação Fase 3

> **Regra que governa esta fase:** competir é opcional, e comparar mal é pior do
> que não comparar. A temporada mede **esforço no período**; o rank continua
> sendo a única medida de desempenho, e nada daqui o alcança.

Escopo entregue: **temporadas**, **ligas por contexto**, e os quatro modos de
desafio — **Boss Battle**, **Sobrevivência**, **Combo** e **Contra o Relógio**.

## Temporadas
1. Temporada é um período com data de início e fim, criado pela administração. Fora de uma temporada aberta não existe placar, e a tela diz isso em vez de inventar uma janela.
2. Janelas ativas **não se sobrepõem**: criar uma temporada dentro de outra é recusado com `season_overlap`.
3. O XP da temporada é **somado do razão** dentro da janela — não há contador paralelo. O valor exibido é sempre igual à soma do extrato que o candidato pode auditar.
4. A tela declara, em texto, que a temporada mede esforço e que quem mede aprendizado é o rank.
5. O fechamento é um ato administrativo explícito. Enquanto ninguém fecha, nada é congelado e o placar segue sendo recalculado.
6. Fechar congela posição, participantes, divisão e contexto em `season_participations`, e a temporada sai do ar.
7. Fechar duas vezes é recusado com `season_already_closed`.
8. O histórico de temporadas do candidato guarda o que ele fez e os prêmios que recebeu, com o critério de cada um.

## Recompensas (item 34: sem loot box)
9. **Nenhuma recompensa é aleatória.** Cada prêmio tem critério verificável, conferido na hora do fechamento.
10. Todo prêmio declara **utilidade em texto**. Prêmio sem utilidade declarada não entra no catálogo.
11. Nenhum prêmio desbloqueia conteúdo de estudo (itens 3 e 24). O selo da temporada declara isso explicitamente: não altera o rank, não rende XP, não desbloqueia nada.
12. O escudo extra — único prêmio com efeito mecânico — vai para os 3 primeiros da divisão e soma uma proteção de sequência.
13. O prêmio **não conquistado aparece com o critério à vista**, em vez de desaparecer da tela.

## Ligas (item 21: comparação por contexto e desligável)
14. A liga reúne candidatos ao **mesmo cargo**. Não existe ranking global.
15. Sem plano vinculado a um cargo, não há liga — e a tela explica o que falta.
16. Abaixo de **5 participantes** não há tabela: a posição entre poucos não significa nada, e isso é dito.
17. Grupos maiores são fatiados em divisões de até **30 candidatos**, ordenadas por XP da temporada. O candidato vê a sua.
18. **Anonimato é o padrão**: quem não escolheu aparecer com nome é exibido como "Candidato #N".
19. O candidato pode escolher um nome de exibição e voltar ao anonimato quando quiser.
20. Desligar a comparação tem efeito **dos dois lados**: quem sai não vê tabela e não aparece na de ninguém.
21. Quem ainda não pontuou participa com zero em vez de sumir — o perfil de gamificação nasce no primeiro ganho, e a ausência dele não exclui o candidato.
22. O empate é desempatado por dias ativos e depois por chave estável: a tabela não troca de ordem a cada carregamento.
23. A tela declara que a liga compara esforço, não domínio, e que sair não afeta nada do estudo.

## Modos de desafio
24. Cada modo declara, por escrito, **como se vence** — e a regra aparece na tela antes de começar.
25. As questões vêm do **banco publicado**. Nenhum modo gera pergunta, altera gabarito ou ajusta dificuldade.
26. Sem questões suficientes, a rodada **não é criada**: `not_enough_questions`, com quantas existem e quantas faltam. Repetir enunciado para completar o número seria fabricar desafio.
27. As questões são congeladas na largada. Uma rodada em andamento não muda de conteúdo entre requisições.
28. Só existe **uma rodada aberta por vez** (`run_already_running`): duas seriam dois placares.
29. O estado da rodada é sempre **derivado das respostas**, nunca acumulado em contador — resposta perdida ou repetida não deixa o placar mentindo.
30. **Boss Battle** enfrenta a disciplina de maior Priority Score. Sem prioridade calculada, o modo é recusado com o motivo e o caminho (`no_priority_score`) — nunca com um sorteio no lugar.
31. A seleção de cada rodada registra **por que** aquelas questões: regra, disciplina e score, visíveis na tela.
32. **Sobrevivência** encerra no terceiro erro e pontua o que foi respondido certo até ali.
33. **Contra o Relógio** encerra ao fim do tempo; o tempo restante nunca fica negativo.
34. **Combo** soma 10% por acerto encadeado, com teto de 2,0×. Um erro zera a sequência e o recorde da rodada é preservado.
35. **Resposta em menos de 3 segundos não alimenta combo nem XP** — mas continua registrada: ela aconteceu.
36. Boss Battle só é vencido com a rodada completa e o alvo de acerto atingido; acertar 5 de 5 e parar não derruba um desafio de 15 questões.
37. Sem resposta alguma, a taxa de acerto é **nula** e não zero por cento, e o XP é zero.
38. Responder numa rodada encerrada é recusado com `run_not_running`.

## XP dos desafios
39. O XP da rodada é a **conta aberta**: XP base do modo × proporção respondida × multiplicador do combo, com cada linha exibida.
40. O ganho passa pelo motor e vira transação no razão, com teto diário próprio e idempotência pela rodada.
41. **Rodada abandonada não pontua** e não gera linha de desafio no extrato: parar no meio não é desempenho.
42. Respostas dadas em desafio contam nas estatísticas reais do candidato, porque são respostas reais. A marca `game_run_id` existe para separá-las na análise, não para escondê-las.

## Qualidade
43. Domínio puro, sem I/O: `challenges.py`, `seasons.py` e `leagues.py` não importam banco, HTTP nem IA.
44. Cobertura: 27 testes de domínio, 25 de integração e 11 de componentes React, todos verdes.
45. `ruff`, `mypy`, `eslint`, `tsc` e `prettier` limpos nos arquivos da fase.
46. A migração sobe e desce sem erro, e `alembic check` não detecta desvio. A coluna `league_opt_out` nasce com default de servidor (para as linhas existentes) e o default é removido em seguida, mantendo modelo e banco alinhados.

# Critérios de Aceite — Gamificação Fase 2

> **Regra que governa esta fase:** telas comparativas comparam **dados reais**.
> Onde a amostra não decide, a tela diz que não decide — nunca desenha um gráfico
> convincente sobre número insuficiente. E nada aqui prevê aprovação.

Escopo entregue: ranks na interface comparativa (histórico), **Você vs Banca**,
**Jornada da Aprovação** e **Mapa do Edital**.

## Histórico de rank
1. Existe uma **foto diária** do rank por candidato (`rank_snapshots`), com score, componentes, sinais ausentes, XP e nível do dia.
2. A gravação é idempotente: várias visitas no mesmo dia produzem **uma** foto, e uma corrida entre requisições não gera duplicata.
3. Com menos de duas fotos, a tela declara que ainda não há evolução — uma medição não é tendência, e `delta` vem nulo.
4. O gráfico mostra queda quando o rank cai. Um número que só sobe não mediria nada.
5. XP e rank aparecem lado a lado no mesmo período, com a diferença escrita: XP mede esforço acumulado, rank mede desempenho.
6. O XP fica em coluna própria do snapshot e **não participa** de nenhum cálculo de rank.

## Você vs Banca
7. A banca do placar é a do **concurso-alvo do plano ativo**. Sem plano, sem concurso ou sem banca no catálogo, a tela explica qual das três coisas falta.
8. O placar é a **taxa de acerto real** do candidato nas questões daquela banca. Os pontos da banca são exatamente as questões erradas — não há adversário simulado nem dificuldade artificial.
9. `você + banca = 100` sempre que há placar; o arredondamento não cria nem perde ponto.
10. Abaixo de **30 respostas** na banca não há placar: a tela mostra quantas respostas existem e quantas faltam.
11. Disciplina abaixo de **30 respostas** não recebe placar próprio — aparece como "amostra insuficiente" com o motivo, e o placar dela não é desenhado.
12. Disciplinas com placar vêm primeiro, ordenadas pela fatia do candidato; as insuficientes ficam no fim.
13. Questões de outras bancas **não entram** no placar; respostas em branco também não.
14. A evolução é agrupada por semana e limitada à janela pedida; com menos de duas semanas, a tela diz que a evolução ainda não existe.

## Jornada da Aprovação
15. Sem plano ativo, a jornada **não inventa marcos**: devolve o motivo e nenhuma etapa.
16. Cada marco tem **critério verificável** e mostra o número real que o cumpre (sessões, questões, simulados, cobertura, dias até a prova).
17. Existe **um único** marco `CURRENT`, e ele é o primeiro pendente.
18. O `ratio` de qualquer marco fica entre 0 e 1 — nada de barra passando de 100%.
19. O marco de reta final só avança quando existe **data de prova** no plano.
20. O aviso "os marcos medem cobertura e desempenho… não são previsão de aprovação" acompanha a jornada **em toda tela** onde ela aparece (item 40 do pedido).
21. Nenhum texto da jornada afirma ou sugere aprovação — testado tanto no domínio quanto na interface.

## Mapa do Edital
22. Cada disciplina do plano vira um território com estado: não iniciada, começou, em andamento, domínio consolidado ou **pede revisão**.
23. O domínio é `0,4 cobertura + 0,4 desempenho + 0,2 retenção`, e cada parcela só entra com amostra (20 respostas, 10 revisões).
24. **Sinal ausente não é penalidade**: o domínio é reescalado pelo peso disponível, para que uma disciplina sem questões cadastradas não pareça abandonada. O que falta é declarado.
25. As parcelas exibidas somam o domínio exibido (dividido pelo peso disponível) — mesma exigência do rank e do Priority Score.
26. Disciplina já dominada e **sem estudo há 21 dias** aparece como "pede revisão", com o número de dias no texto. É o estado que um gráfico de cobertura esconderia.
27. O mapa é ordenado do território **mais frágil ao mais consolidado**: a tela abre no que precisa de atenção.
28. Sem plano, o mapa não existe e a tela diz por quê.

## Interface
29. `/voce-vs-banca` e `/jornada` são rotas próprias, com carregamento sob demanda e itens no menu.
30. Toda barra de placar tem descrição textual para leitor de tela.
31. Os blocos "por quê?" abrem a composição do rank e do domínio de cada território.
32. Nenhuma tela desta fase usa mascote, efeito exagerado ou linguagem de ameaça (itens 35 e 40).

## Qualidade
33. Domínio puro, sem I/O: `board_battle.py`, `journey.py` e `territory.py` não importam banco, HTTP nem IA.
34. Cobertura de testes: 20 testes de domínio, 13 de integração e 11 de componentes React, todos verdes.
35. `ruff`, `mypy`, `eslint`, `tsc` e `prettier` limpos nos arquivos da fase.
36. A migração `rank_snapshots` sobe e desce sem erro, e `alembic check` não detecta desvio.

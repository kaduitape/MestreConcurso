# Critérios de Aceite — Fase 9 (Analytics)

> **Regra que sustenta a fase**, e que o backlog já pedia: **cada gráfico tem uma
> decisão associada, e os intervalos estão sempre visíveis.** Um número sem faixa
> é uma afirmação; um gráfico sem decisão é enfeite caro.

## Estatística
1. Todo cálculo com incerteza vive em `app/domain/analytics/statistics.py`, em Python determinístico. **A IA nunca é responsável sozinha por cálculo estatístico.**
2. O intervalo usado é o de **Wilson**, e não o normal simples: com amostra pequena ou proporção extrema, o normal produz limites impossíveis (−4%, 108%) e uma falsa precisão.
3. Os valores conferem com o intervalo de Wilson publicado (70/100 → 0,604–0,781) e nunca saem de [0, 1].
4. Sem amostra, a faixa é [0, 1] e a confiança é `NONE`. Zero de zero **não** é zero por cento — é não saber.
5. Uma resposta certa não sustenta afirmar domínio: 1/1 devolve limite inferior abaixo de 30%.
6. Mais amostra estreita a faixa, e a confiança sobe em degraus declarados (`LOW` < 30, `MEDIUM` < 300, `HIGH` daí em diante).
7. Num índice composto, **sinal ausente reescala em vez de penalizar**: o índice é dividido pelo peso que existia, e o que falta é declarado.
8. A confiança de um composto é a do **sinal mais frágil** — um índice não é mais confiável que a sua pior parcela.

## Mestre Score
9. Vai de 0 a 1000 e mede competência real: 30% acerto, 20% retenção, 25% cobertura, 15% simulados, 10% consistência.
10. **XP não entra.** A separação é estrutural: `MasterScoreInput` não tem campo de XP nem de nível, então não depende de ninguém lembrar da regra.
11. As parcelas exibidas **somam exatamente** o valor exibido (arredondamento por maior resto), como no Priority Score e no rank.
12. O score sai **sempre com faixa**, e a interface a desenha — a barra mostra o intervalo como região e o valor central como traço.
13. Cada sinal tem amostra mínima; abaixo dela ele não entra e a tela diz quanto falta.
14. Candidato sem dados **não recebe nota zero**: recebe a ausência declarada, com o que falta em cada sinal.
15. Quando parte dos sinais falta, o peso disponível é exibido ("50% dos sinais têm amostra").
16. **O score pode cair.** Um índice de competência que só sobe mede tempo de cadastro, não competência.
17. O texto que acompanha a faixa diz o que ela é — propagação de Wilson pelos pesos — e que **não é probabilidade de aprovação**.
18. Existe foto diária (`master_score_snapshots`) com valor **e faixa**, e a evolução só aparece a partir do segundo dia.
19. O perfil de gamificação passa a exibir o Mestre Score real, lido de Analytics e nunca recalculado ali.

## Se a prova fosse hoje
20. Estima **nota**, nunca aprovação. Não há probabilidade de passar nem comparação com nota de corte — a plataforma não tem esse dado oficial.
21. Sem distribuição oficial de questões por disciplina, **não há estimativa** — e o motivo é dito.
22. Disciplina com menos de 20 respostas fica de fora, com quantas faltam.
23. A estimativa declara **qual fatia da prova ela cobre**, sempre, e a barra de cobertura fica ao lado do número.
24. Abaixo de 50% de cobertura, **nenhum total é afirmado**: a tela mostra as disciplinas e o que falta, não um número menor.
25. O total sai com faixa (limites de Wilson propagados pelas questões e pelos pesos).
26. Nota mínima do edital vira **alerta** quando o limite inferior da faixa não a alcança, e a disciplina em risco é listada primeiro.
27. O aviso de que isto não é previsão de resultado aparece na tela, não só na documentação.

## Caminho da aprovação
28. As ações são ordenadas por **quantas questões da prova elas colocam em jogo** (questões × peso × espaço de melhora).
29. **Todo passo carrega o número que o gerou.** Recomendação sem número é palpite, e palpite com cara de sistema é pior que palpite.
30. Disciplina sem amostra vira ação de **medir**, com quantas questões faltam — e sem ganho estimado, porque ainda não se sabe onde o candidato está.
31. Disciplina consolidada vira **manutenção**, com a recomendação explícita de investir o esforço em outra.
32. Risco de eliminação vem primeiro na ordem.
33. O rodapé declara que seguir a lista melhora o que é medido e **não é garantia de resultado**.

## Painéis
34. São quatro: evolução do acerto, retenção, cobertura por disciplina e consistência.
35. **Todo gráfico declara a decisão que ele serve** — inclusive quando está vazio. É o critério de aceite da fase, verificado em teste.
36. Gráfico sem dado **explica a ausência** em vez de desenhar zeros.
37. Séries de proporção trazem faixa e amostra em cada ponto, e a interface desenha a faixa como região sombreada: duas semanas com o mesmo acerto e amostras diferentes ficam visivelmente diferentes.
38. Os pontos saem em ordem cronológica.
39. O painel de cobertura declara que cobertura é tempo cumprido sobre tempo planejado — **não é domínio**.

## Qualidade
40. Domínio puro, sem I/O: nada em `app/domain/analytics/` importa banco, HTTP ou IA. O serviço só consulta e entrega números crus.
41. Cobertura: 37 testes de domínio, 13 de integração e 15 de componentes React, todos verdes.
42. `ruff`, `mypy`, `eslint`, `tsc` e `prettier` limpos nos arquivos da fase.
43. A migração sobe e desce sem erro, e `alembic check` não detecta desvio.

# Critérios de Aceite — Fase 8 (Memorização)

> Regra que atravessa a fase: **a fila nunca explode.** Quem some por uma semana
> volta e encontra uma sessão que dá para terminar — não uma dívida impagável.
> Fila que vira dívida é o jeito mais rápido de fazer alguém abandonar a revisão.

## Intervalos
1. O intervalo sai de conta determinística em Python. Nenhuma IA decide quando um cartão volta.
2. Cartão novo passa por passos de aprendizado antes de virar revisão; "Fácil" pula direto para revisão.
3. Em revisão, o intervalo cresce pela facilidade do cartão (SM-2), que se move entre 1,3 e 3,0 e nunca sai dessa faixa.
4. As quatro respostas produzem intervalos estritamente crescentes: **Não lembrei < Difícil < Lembrei < Fácil**.
5. Existe teto de 180 dias: às vésperas da prova, nenhum cartão pode sumir por dois anos.
6. **Toda revisão devolve o `breakdown`** que explica o número — intervalo anterior, fator aplicado, ajuste de velocidade e teto, quando houver. A interface mostra isso; o candidato nunca recebe um número seco.

## Erro
7. Errar **não zera** o progresso: o intervalo cai a uma fração do anterior, com piso de 1 dia.
8. Por isso, quem erra um cartão maduro mantém mais terreno do que quem erra um cartão recém-visto — o histórico de acertos vale alguma coisa.
9. Erro em cartão ainda em aprendizado devolve o cartão para o mesmo dia.
10. O cartão vai para `RELEARNING` e o contador de lapsos sobe: o histórico de dificuldade fica registrado.

## Velocidade
11. **A velocidade da resposta ajusta o intervalo**, limitada a ±15%: responder rápido e certo demonstra domínio maior do que acertar hesitando.
12. O ajuste **não se aplica a erro**: responder "não lembrei" em um segundo não é domínio, é não ter tentado.
13. Sem tempo medido, o intervalo fica intacto — a ausência do dado não vira penalidade.

## A fila que não explode
14. A fila tem teto diário (60 por padrão, configurável até 300). Acima disso a sessão deixa de ser revisão e vira maratona, que ninguém repete no dia seguinte.
15. O que passa do teto é **redistribuído pelos próximos dias** (até 7), do mais atrasado para o menos — e a mudança é gravada, então amanhã o candidato não reencontra a mesma avalanche.
16. A fila informa em texto o que aconteceu: quantos dias de ausência, quantos estavam vencidos, quantos ficaram para hoje e quantos foram redistribuídos.
17. **Revisão vencida tem precedência sobre cartão novo**: memória que já existe e está prestes a se perder vale mais do que memória que ainda nem começou.
18. Cartões novos entram só no espaço que sobra sob o teto, respeitando o limite diário de novos.
19. Cartão com vencimento futuro não é puxado para hoje.
20. Empate entre cartões igualmente atrasados é desfeito pelo **Priority Score da disciplina** (Fase 6).
21. Adiar a fila é uma **escolha declarada** ("não vou conseguir hoje"), não um acúmulo silencioso.
22. A previsão dos próximos dias é exibida antes de a carga chegar.

## Flashcards
23. O cartão declara sua origem: escrito pelo candidato, gerado por IA, vindo de uma questão, de um erro do Caderno de Erros, do edital ou de curadoria da equipe.
24. Frente repetida no mesmo baralho é recusada (comparação normalizada).
25. Cartão criado a partir de uma **questão errada** guarda a referência e traz no verso o gabarito com o comentário da alternativa correta.
26. Cartão criado a partir de um **erro classificado** herda a disciplina e a referência do erro.
27. Cartão e **estado de memória** são tabelas distintas: um cartão global é revisado por muita gente, e cada pessoa tem seu próprio intervalo.
28. Cada candidato só edita e remove os próprios cartões; cartão global é somente leitura para ele.

## Geração por IA
29. A IA gera cartões **apenas** a partir do material fornecido, e cada cartão precisa citar um trecho literal dele.
30. **Cartão cuja citação não aparece no material é descartado**, não salvo com aviso: um verso sem base entraria na repetição espaçada e seria memorizado por insistência.
31. Os descartados são informados ao candidato, com a frente de cada um — o que a plataforma jogou fora é dito.
32. Cartão gerado nasce marcado como `AI`, com modelo e versão de prompt, e carrega a citação e o documento de origem.
33. Material curto demais é recusado **antes** de qualquer chamada ao modelo: não se paga token para gerar do nada.
34. A segunda geração do mesmo material sai do cache; cartões repetidos não são duplicados.
35. O material vai ao modelo dentro de `<material>`, com instrução de que aquilo é dado e não instrução.

## Estatística
36. Os números vêm da contagem de revisões reais: total de cartões, vencendo hoje, consolidados, revisados hoje e distribuição por resposta.
37. **Sem revisão registrada, a taxa de recordação é nula, não zero** — zero seria outra afirmação.

## Interface
38. **Revisão** — cartão por vez, com "mostrar resposta" antes das quatro opções; barra de progresso; e, depois de responder, a frase "você verá este cartão de novo em N dias" seguida da explicação do cálculo.
39. O cabeçalho da sessão mostra o resumo da fila (vencidos, redistribuídos, ausência) em texto.
40. **Revisão relâmpago** é a mesma fila truncada, para que a sessão curta não desalinhe o agendamento.
41. **Flashcards** — baralho com selo de origem por cartão, citação quando houver, filtro por origem e a carga dos próximos 14 dias.
42. A geração por IA mostra quantos cartões entraram e quantos foram descartados, com o motivo.

## Qualidade
43. `pytest` verde (377 testes), sendo 46 desta fase — 26 unitários (intervalos, velocidade, fila) e 20 de integração.
44. `ruff`, `ruff format` e `mypy` sem erro no backend.
45. `tsc`, `eslint` e `vitest` (94 testes) verdes no frontend; `vite build` conclui.
46. Migração da Fase 8 cria `flashcards`, `flashcard_states` e `flashcard_reviews`, e reverte limpo.

## Ressalvas honestas desta entrega
- O algoritmo é da **família SM-2**, com acréscimos deliberados (velocidade, teto, queda proporcional). Não é FSRS: FSRS depende de um modelo treinado sobre histórico de revisões, e este banco ainda não tem histórico para treinar coisa alguma. Trocar de algoritmo depois é possível — o cálculo está isolado em `app/domain/srs/`, sem I/O.
- A **fila de revisão unificada** prevista no modelo (`revision_queue`, com tópicos, questões e vocabulário no mesmo lugar) não foi construída: esta fase entrega a fila de **flashcards**. Unificar exige decidir como um tópico "vence", o que pertence à Fase 9.
- Cartões **globais** (curados pela equipe) são suportados pelo modelo e pela consulta, mas não há tela de administração para criá-los; hoje todo cartão nasce de um candidato.
- A geração por IA aceita material **colado**. Gerar direto de um trecho do edital indexado é o passo natural seguinte e depende de uma seleção na tela do Raio-X, que não entrou aqui.
- As migrações foram geradas e conferidas contra SQLite (o ambiente não tem daemon Docker); a revisão para MySQL foi manual, como nas fases anteriores.

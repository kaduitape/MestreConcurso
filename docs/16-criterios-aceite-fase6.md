# Critérios de Aceite — Fase 6 (Inteligência)

> Regra que atravessa a fase inteira: **todo score exibido abre o "POR QUÊ?" com
> contribuições que somam o valor mostrado, e nenhuma estatística aparece sem a
> amostra que a sustenta.**

## Mapa de incidência
1. A incidência de cada disciplina é a fatia das questões cadastradas daquela banca — contagem em Python, nunca estimativa.
2. Abaixo de **30 questões da banca** o mapa não é publicado: a resposta traz o motivo com o número que falta, e a tela mostra esse motivo em vez de um vazio.
3. Dentro de uma amostra válida, o recorte com menos de **5 questões** é descartado — publicar 1 questão como "2% de incidência" seria ruído.
4. A soma das fatias publicadas fecha em 100% da amostra, e cada linha exibe "N de M questões".
5. A tendência só existe com **dois anos distintos** na amostra; sem isso o campo é nulo e a tela diz que não há histórico — "estável" seria afirmação sem base.
6. Cada linha carrega período, número de provas e confiança, que cresce com a amostra e satura em 1.
7. O recálculo apaga e regrava os recortes da banca: um número que perdeu amostra desaparece em vez de envelhecer no banco.

## DNA da banca
8. As métricas (distribuição por dificuldade, formato das questões, disciplinas mais cobradas, alternativas por questão) são contagem sobre o banco — nenhuma vem de interpretação de modelo.
9. Abaixo de **30 questões** o perfil não é traçado, e o motivo é devolvido junto.
10. Cada métrica exibe a amostra (questões e provas) e o período ao lado do valor.
11. A leitura *qualitativa* da banca continua em `board_knowledge`, marcada como interpretação de IA: cálculo e interpretação nunca aparecem misturados na mesma seção.

## Priority Score
12. O score vai de 0 a 100 e sai de cinco sinais com teto próprio: incidência na banca (30), peso no edital (25), seu desempenho (25), tempo sem estudar (12) e conteúdo pendente (8).
13. **As parcelas somam exatamente o score exibido** — o arredondamento usa o método do maior resto, então não há "≈" na interface.
14. Cada parcela traz o dado que a gerou em texto ("18,0% das questões da banca", "44,0% de acerto em 40 respostas").
15. Sinal ausente vale **zero e é declarado** em `missing_signals`; a parcela mostra por que não entrou ("sem amostra de questões da banca", "disciplina fora do edital do cargo").
16. O desempenho só entra a partir de **5 respostas** na disciplina; abaixo disso a parcela é zero e diz qual é o mínimo.
17. `coverage` informa a fração de sinais disponíveis: é a confiança do próprio score, exibida junto dele.
18. Errar mais eleva a prioridade; acertar mais a reduz, mantidos os demais sinais.
19. Sem plano ativo, o cálculo devolve lista vazia **com a explicação** — nunca uma lista de zeros.

## Efeito no plano de estudo
20. Com Priority Score calculado, a divisão do tempo se inclina na direção dele em **no máximo 20%** por disciplina: o desempenho ajusta o plano, não o substitui.
21. Disciplina sem score mantém exatamente a fatia da linha de base do edital.
22. A soma das fatias continua fechando em 100% do tempo disponível depois do ajuste.
23. O `score_breakdown` da tarefa ganha `prioridade_por_desempenho` e `ajuste_de_tempo`, e o "por quê?" da missão passa a dizer quanto tempo a disciplina ganhou ou perdeu em relação ao edital puro.
24. Sem score, nada muda no plano — e a interface continua dizendo que a personalização por desempenho ainda não entrou.

## Caderno de Erros
25. Toda questão errada entra numa fila de classificação, com enunciado, disciplina e a letra marcada.
26. A causa vem de uma taxonomia fechada de sete opções; causa fora da lista é recusada.
27. Causa **declarada pelo candidato** nasce confirmada e conta na hora.
28. A IA pode sugerir a causa: a sugestão é gravada com origem `AI`, modelo e versão de prompt, **e não entra em estatística alguma** enquanto não for confirmada.
29. O candidato pode confirmar a sugestão ou substituí-la — substituir grava a causa como `USER`.
30. O padrão de pegadinha só é aceito quando a causa é "caí numa pegadinha"; fora disso é recusado com motivo.
31. Pegadinha sugerida pelo modelo fora do catálogo é descartada — nome de armadilha inventado não vira registro.
32. Questão respondida corretamente não pode ser classificada como erro.
33. Cada causa tem uma ação associada, fixa e ligada à causa — não é texto gerado.
34. A causa predominante do caderno só é apontada a partir de **5 erros classificados**; por disciplina, a partir de 3. Empate não tem dominante.
35. Erro marcado como superado permanece no histórico e é contado à parte.
36. O caderno de um candidato é inacessível a qualquer outro (404).

## Radar de Pegadinhas
37. O catálogo de padrões é editorial e sincronizado no seed: são **categorias de técnica de prova**, não afirmações sobre nenhuma banca.
38. O radar só aponta um padrão a partir de **3 erros** marcados com a mesma armadilha; abaixo disso a tela explica o critério em vez de mostrar uma lista com um item.
39. A contagem do radar é sobre os erros confirmados do próprio candidato.

## Simulado adaptativo (fecha a pendência da Fase 5)
40. O adaptativo distribui as questões conforme o Priority Score já calculado, e registra as cotas em `config`.
41. Sem Priority Score, ele é recusado com o motivo e o caminho ("monte o plano e resolva algumas questões") — nunca um simulado genérico disfarçado de adaptativo.

## Interface
42. **Inteligência** — mapa de incidência com amostra e tendência por linha, DNA da banca com a amostra de cada métrica, e o painel de prioridades.
43. Cada disciplina do painel abre as parcelas com barra proporcional, o texto de origem e o aviso de quantos sinais ainda não existem.
44. **Meus erros** — caderno com causas, disciplinas e radar; fila de classificação; aba separada para as sugestões da IA ainda não confirmadas, rotuladas como sugestão.
45. **Admin → Questões** ganha o recálculo de incidência e DNA, com o relatório por banca, inclusive o motivo de cada recorte bloqueado.
46. Nenhum número exibido é estimado: onde falta amostra, a tela diz que falta amostra.

## Qualidade
47. `pytest` verde (298 testes), sendo 37 desta fase — 18 unitários do cálculo (incidência, Priority Score, perfil e caderno) e 19 de integração.
48. `ruff`, `ruff format` e `mypy` sem erro no backend.
49. `tsc`, `eslint` e `vitest` (74 testes) verdes no frontend; `vite build` conclui.
50. Migração da Fase 6 cria `topic_incidence`, `board_profile_metrics`, `trap_patterns`, `error_analyses` e `user_priorities`, e reverte limpo.

## Ressalvas honestas desta entrega
- A incidência é calculada por **disciplina**. O recorte por assunto existe no modelo (`topic_id`) e no domínio (`by_topic`), mas as questões só carregam assunto quando alguém as classifica nesse nível — publicar incidência por assunto sobre um banco sem assunto seria inventar granularidade.
- O Priority Score é por **disciplina**. O recorte por assunto está previsto na tabela (`topic_id`) e entra quando houver classificação por assunto no banco de questões.
- O catálogo de pegadinhas é ponto de partida editorial e não afirma nada sobre banca alguma. Associar um padrão a uma banca específica exigiria amostra de questões classificadas — não existe ainda, e por isso não é afirmado.
- O Mestre Score (0–1000) do wireframe pertence à Fase 9 (Analytics); esta fase entrega os sinais que o alimentam, não o número.
- As migrações foram geradas e conferidas contra SQLite (o ambiente não tem daemon Docker); a revisão para MySQL foi manual, como nas fases anteriores.

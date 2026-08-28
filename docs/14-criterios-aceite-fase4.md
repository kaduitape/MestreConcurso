# Critérios de Aceite — Fase 4 (Estudo)

## Planejador (regras puras, sem IA)
1. A disponibilidade é declarada em minutos por dia da semana; valores fora de 0–960 e dias inválidos são recusados.
2. O calendário respeita os dias sem tempo e os dias bloqueados; fim de semana sem disponibilidade não recebe tarefa.
3. A fatia de cada disciplina sai de três sinais normalizados — **peso no edital (45%)**, **questões na prova (35%)** e **extensão do conteúdo (20%)** — e a soma das fatias fecha em 100% do tempo disponível.
4. Disciplina com peso maior recebe mais tempo; nenhuma disciplina do edital fica com zero minuto (piso de 2%).
5. Cada tarefa guarda o `score_breakdown` que a colocou ali; a interface exibe isso no "por quê?" — nenhum texto é inventado.
6. O dia é dividido por tipo de atividade (teoria, questões, revisão, flashcards) e nunca ultrapassa a capacidade declarada.
7. Nenhum bloco abaixo de 15 minutos é criado: tarefa curta demais não vira compromisso.
8. A menos de 30 dias da prova a composição muda sozinha — teoria cai de 45% para 20%, questões e revisão sobem.

## Replanejamento (a regra do "nunca acumular")
9. Tarefa pendente de dia passado é remarcada para os dias que ainda existem, mais antiga primeiro.
10. Cada dia absorve no máximo 20% além da disponibilidade declarada; o que não couber é **removido do plano**, não empilhado.
11. Cada remarcação encurta a tarefa (fator 0,7) e, após duas, ela sai do plano — repetir indefinidamente não ajuda ninguém.
12. Depois do replanejamento, nenhuma tarefa continua "pendente no passado": ou foi remarcada, ou foi declarada como removida.
13. O resultado informa quantas foram remarcadas e quantas saíram, em texto claro para o candidato.

## Plano e agenda
14. `POST /study/plan` monta o plano a partir de um **cargo cadastrado** ou de um **edital confirmado**; sem origem, responde `plan_source_required`.
15. Concurso com prova em data passada é recusado com mensagem explícita, em vez de gerar uma agenda impossível.
16. Um plano ativo por vez: criar outro arquiva o anterior, preservando o histórico.
17. Atualizar a disponibilidade regenera **apenas o futuro pendente**; o que já foi feito permanece como histórico.
18. `GET /study/today` devolve a missão do dia com tempo planejado, tempo cumprido e número de atrasos.
19. `GET /study/calendar` agrupa por dia, e o total de cada dia bate com a soma das tarefas não removidas.
20. Sem plano, os endpoints respondem `no_active_plan` e a interface convida a montar o plano — nunca mostra agenda vazia sem explicação.

## Sessões (cronômetro)
21. Só existe uma sessão em andamento por vez; tentar abrir outra devolve `session_already_running` com o identificador da atual.
22. Pausa e retomada são registradas: o tempo pausado entra em `pause_seconds` e **não** conta como foco.
23. Ao encerrar, o tempo de foco é somado à tarefa e ao progresso da disciplina; cumprido o tempo planejado, a tarefa é concluída automaticamente.
24. Cronômetro esquecido aberto é limitado a 6 horas — dois dias de sessão não viram 48 horas de estudo.
25. "Estudado em 7 dias" soma tempo real de foco, sem estimativa.

## Modo Sprint
26. `POST /study/sprint` monta blocos que somam exatamente o tempo informado.
27. Sprint de 15 minutos não abre conteúdo novo (só revisão e flashcards); sprint de 60 prioriza questões.
28. A sobra de arredondamento vai para o bloco de maior peso, não para o último da lista.
29. Duração abaixo de 15 minutos é recusada.

## Interface
30. A página "Hoje" mostra a missão real: disciplinas, tipo de atividade, duração e o que já foi cumprido.
31. Cada tarefa abre o "por quê?" com os números do planejador e diz explicitamente que a priorização por desempenho chega na Fase 6.
32. Atraso aparece como alerta com ação de replanejar, não como acúmulo silencioso.
33. O calendário mostra quatro semanas, marca o dia atual e a data da prova.
34. Estados vazios, de carregamento e de erro cobertos; nenhum dado fictício.

## Qualidade
35. `pytest` verde (222 testes), com 31 só do planejador — alocação, agenda, sprint e replanejamento.
36. `ruff` e `mypy` sem erro; `tsc`, `eslint` e `vitest` (53 testes) verdes no frontend.
37. Migração da Fase 4 aplica e reverte limpo.

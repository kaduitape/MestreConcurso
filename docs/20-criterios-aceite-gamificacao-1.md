# Critérios de Aceite — Gamificação Fase 1

> **Regra que governa a camada:** XP mede esforço útil; rank mede desempenho
> real; nenhum dos dois mede cliques. Todo ganho é auditável e todo corte é
> explicado.

## Motor e configuração
1. O motor recebe **eventos de domínio consumados** e decide a pontuação; nenhum serviço de estudo, questão ou revisão contém regra de XP.
2. As regras vivem na tabela `game_rules`: valor, teto diário e liga/desliga por evento. O código traz apenas o padrão de fábrica, usado quando não há linha.
3. Alterar uma regra no painel muda a pontuação **sem deploy**, e a alteração registra quem alterou.
4. Desligar um evento no painel faz o motor deixar de pontuá-lo, sem quebrar o fluxo que o emitiu.

## XP e razão contábil
5. **Todo ganho vira uma transação** (`xp_transactions`) com evento, valor base, multiplicador, motivo e a métrica que o justificou. O saldo do perfil é sempre reconstruível somando o razão.
6. O extrato de XP é visível ao candidato: ele consegue ver de onde veio cada ponto.
7. Pontuação é **idempotente por referência**: o mesmo simulado, sessão ou missão nunca pontua duas vezes, mesmo com chamada repetida.

## Antiabuso
8. **Teto diário por evento.** Atingido o teto, o ganho é zerado, a transação é gravada com `capped=true` e o motivo aparece para o candidato — não some em silêncio.
9. **Sessão com menos de 5 minutos de foco vale zero.** Abrir e fechar tela não é estudo.
10. **Questão respondida em menos de 3 segundos não entra na contagem**: não dá tempo de ler o enunciado.
11. **Questão repetida no mesmo dia não repontua.**
12. A dificuldade modula o XP (fácil 0,7× · difícil 1,3×): responder cem questões fáceis não vale mais do que estudar de verdade.
13. Lote com menos de 40% de acerto recebe 0,6× — o objetivo é aprender, não preencher contador.
14. O XP de estudo usa o **tempo de foco** da sessão, que já exclui pausa (Fase 4). Tempo ocioso nunca vira XP.

## Níveis
15. A curva de níveis é crescente e configurável; o perfil informa XP no nível atual e quanto falta para o próximo.
16. Subir de nível **não desbloqueia conteúdo de estudo** — apenas reconhecimento e personalização (item 3 do pedido).

## Rank
17. O rank sai da fórmula de desempenho: 30% acerto, 25% retenção, 20% cobertura, 15% simulados, 10% consistência. **XP não entra.**
18. Cada componente vem de dado real e tem **amostra mínima**; sem amostra vale zero e é declarado como "ainda sem amostra".
19. As contribuições exibidas **somam o score mostrado** — mesma exigência do Priority Score.
20. O rank **pode cair**, e a queda é comunicada com o componente que recuou, sem linguagem de punição.
21. Candidato sem dados é FERRO **porque ainda não há o que medir**, e a tela diz isso — não sugere que ele seja ruim.

## Streak
22. O dia só conta com **estudo útil**: 20 minutos de foco, ou a missão do dia concluída, ou 3 tarefas do plano.
23. Guardamos atual, recorde, média e histórico dia a dia.
24. **Duas proteções por mês**, renovadas no dia 1: um dia perdido consome uma proteção e a sequência sobrevive.
25. Sem proteção disponível, a sequência quebra e o texto é factual — o recorde continua registrado. Nada de linguagem de perda ou ameaça.

## Missões
26. As missões do dia nascem de **sinal real**, na ordem: revisão vencida → erros sem causa → maior Priority Score → tarefa do plano → volume de questões.
27. **Toda missão carrega o `rationale`** com o número que a gerou, exibido como "por quê?" no card.
28. O progresso é medido pela atividade real do candidato, não por marcação manual.
29. Missão concluída libera o resgate do XP; o resgate é idempotente.
30. O bônus diário só é liberado com **todas** as missões do dia concluídas.
31. Sem plano de estudo ativo, a Central mostra o convite a montar o plano — **nunca missões inventadas**.
32. Missão expira no fim do dia e não acumula: fila de missão vencida repetiria o erro que a Fase 8 evitou na revisão.

## Conquistas
33. As conquistas são avaliadas sobre dados reais (horas, questões, acerto, sequência, cartões, erros classificados).
34. Conquista secreta não aparece antes de desbloqueada; a lista mostra que existem secretas, sem revelá-las.
35. Conquista desbloqueada concede XP uma única vez e registra a data.
36. O progresso das conquistas visíveis é exibido (ex.: 8/25), com o número real.

## Interface
37. **Central de Missões** — progresso do dia, XP de hoje, cards com prioridade, tempo estimado, recompensa, barra de progresso e o "por quê?".
38. **Perfil** — nível com barra, rank com as contribuições abertas, sequência com recorde/média/proteções, totais reais e conquistas.
39. A **tela Hoje** ganha a faixa com sequência, nível, rank e progresso diário, sem empurrar a missão do dia para baixo da dobra.
40. Animações discretas: *count-up* no XP, anel de progresso, brilho ao subir de nível, confete curto só em conquista. Todas respeitam `prefers-reduced-motion`.
41. Nenhum botão decorativo: todo elemento clicável executa ação real.
42. **Nenhuma tela afirma ou sugere aprovação.** O vocabulário é progresso, domínio, preparação e desempenho estimado.

## Painel administrativo
43. O painel lista as regras vigentes com valor, teto e estado, e permite editar cada uma.
44. A edição é auditada (quem, quando, valor anterior).

## Qualidade
45. `pytest` verde (436 testes), sendo 59 desta camada — 39 unitários (XP, antiabuso, níveis, rank, sequência, missões, conquistas) e 20 de integração.
46. `ruff`, `ruff format` e `mypy` sem erro no backend.
47. `tsc`, `eslint` e `vitest` (107 testes) verdes no frontend; `vite build` conclui.
48. A migração da Gamificação Fase 1 cria `game_rules`, `gamification_profiles`, `xp_transactions`, `missions`, `achievements`, `user_achievements` e `streak_days`, e reverte limpo.

## Ressalvas declaradas
- O **Mestre Score** (item 23 do pedido) pertence à Fase 9 do backlog e **não existe ainda**. O perfil reserva o lugar dele e declara isso na tela; o ponto de integração está definido, e a regra "XP não alimenta o Score" já está garantida por construção — o Score não lê o razão de XP.
- **Você vs Banca, Jornada, Mapa do Edital, temporadas, ligas, Boss Battle, Sobrevivência, Combo, Contra o Relógio, desafios sociais, card compartilhável e eventos especiais** ficam para as fases G2–G4, conforme o próprio pedido (item 41). Nada disso aparece como botão inerte na interface.
- A **missão especial gerada por IA** (item 7) não entra na G1: o gerador de missões da G1 é determinístico. A arquitetura já prevê `generated_by=AI`, e a IA entrará redigindo o texto sobre objetivos que o Python calcula.

# Critérios de Aceite — Gamificação Fase 4

> **Regra que governa esta fase:** aqui os números do candidato saem da
> plataforma — para um adversário, um evento coletivo ou um link publicado. É o
> ponto onde exagerar seria mais fácil e mais caro. Nada sai sem amostra, sem
> pedido explícito e sem poder ser desfeito.

Escopo entregue: **desafio entre amigos**, **eventos especiais**, **Modo Guerra**
e **card compartilhável**.

## Desafio entre amigos
1. Os dois lados respondem **exatamente as mesmas questões**, congeladas na criação do convite. Listas diferentes comparariam sortes, não candidatos.
2. Sem questões suficientes no banco, o convite não é criado (`not_enough_questions`) e o número que falta é dito.
3. O convite é um código curto, sem caracteres que se confundem ao ler em voz alta, e expira em 48 horas.
4. **Não existe adversário simulado.** Sem alguém que aceite, não há placar — o duelo expira.
5. O resultado só é declarado quando **os dois lados terminam**; até lá o estado é indefinido e a tela diz por quê.
6. Prazo esgotado com um lado parado produz **vitória por ausência**, dita com esse nome, e a tela registra que isso não mede desempenho comparado.
7. Prazo esgotado sem ninguém concluir não produz vencedor.
8. Empate em acertos é desempatado pelo tempo total, e o desempate é declarado na tela.
9. Empate completo é empate — não há critério inventado para forçar um vencedor.
10. Ninguém aceita o próprio desafio (`cannot_duel_yourself`) nem um desafio já aceito (`duel_already_taken`).
11. Um duelo é privado aos seus dois lados: para qualquer outro usuário ele não existe (404).
12. Cada lado tem a sua rodada, e as respostas contam nas estatísticas reais como qualquer outra.

## Eventos especiais
13. Um evento é uma janela com metas medidas nas **mesmas métricas do resto da plataforma** — minutos de foco, questões, revisões, desafios, dias qualificados. A lista é fechada: métrica desconhecida é recusada.
14. Métrica exclusiva de evento não existe. Um número que só valesse dentro do evento seria fabricado para gerar urgência.
15. Meta zerada ou evento sem meta são recusados.
16. **Prêmio sem utilidade declarada é recusado na criação.** Se há rótulo, há explicação do que ele faz.
17. O evento só é cumprido com **todas** as metas atingidas; o progresso parcial aparece meta a meta.
18. O progresso vem da atividade real do candidato dentro da janela, e é recalculado a cada leitura.
19. A tela declara que participar é opcional e que o evento não altera o rank.
20. Eventos podem coexistir — ao contrário das temporadas, que não se sobrepõem.

## Modo Guerra
21. É um período **declarado pelo candidato**: ele escolhe os dias e a meta diária. A plataforma não impõe nem sugere números.
22. Períodos fora dos limites (3 a 30 dias) e metas diárias abaixo do mínimo são recusados com o motivo.
23. A meta é confrontada com o **histórico real** do candidato: se pede o dobro da média recente, a tela avisa — e deixa começar. Avisar não é bloquear.
24. **Sem histórico não há aviso.** Inventar uma média para poder alertar seria fabricar número.
25. O acompanhamento é dia a dia, a partir de minutos e questões reais.
26. O **dia corrente não conta como perdido**: ele ainda pode ser cumprido.
27. Um dia só é cumprido quando **as duas metas** (minutos e questões) são atingidas.
28. As mensagens descrevem sem julgar: nenhuma variação de "falhou", "fracassou" ou "você não conseguiu" (item 40).
29. Um período encerrado com falhas ainda reconhece o que foi feito: "o que foi estudado continua valendo".
30. Só existe um Modo Guerra em andamento por vez; encerrado, outro pode começar.
31. Encerrar antes do fim registra o resultado real, sem marcar sucesso.

## Card compartilhável
32. **Nada é publicado por padrão.** O card só existe quando o candidato pede.
33. O candidato escolhe campo a campo o que entra.
34. **Estatística sem amostra mínima não entra** (30 respostas, 20 revisões, plano ativo para cobertura) — e o motivo aparece na lista "fora do card", em vez de a lacuna ser escondida.
35. Nenhum texto do card afirma, sugere ou insinua aprovação. Há uma verificação literal contra uma lista de expressões proibidas, e ela roda antes de o card existir.
36. O rodapé declara que os números medem estudo e desempenho, **não resultado em prova**.
37. O conteúdo é **congelado na publicação**: o link mostra os números daquele dia e não muda sozinho depois que alguém já o compartilhou.
38. O link público depende de um segredo de 32 bytes e não devolve o próprio token.
39. O card pode ser **revogado** a qualquer momento; revogado, o link deixa de encontrar qualquer coisa.
40. A prévia não publica nada — mostra o que entraria e o que ficaria de fora.

## Qualidade
41. Domínio puro, sem I/O: `duels.py`, `events.py`, `war_mode.py` e `share_card.py` não importam banco, HTTP nem IA.
42. Cobertura: 35 testes de domínio, 18 de integração e 9 de componentes React, todos verdes.
43. `ruff`, `mypy`, `eslint`, `tsc` e `prettier` limpos nos arquivos da fase.
44. A migração sobe e desce sem erro, e `alembic check` não detecta desvio.

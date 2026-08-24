# Critérios de Aceite — Fase 5 (Questões e Simulados)

## Banco de questões
1. A questão só é aceita com **exatamente um gabarito**; zero ou dois gabaritos devolvem `invalid_correct_alternative` com a contagem encontrada.
2. Menos de duas alternativas (`not_enough_alternatives`) e letras repetidas (`duplicate_letter`) são recusados antes de gravar.
3. Enunciado repetido é detectado por *checksum* normalizado (espaços e caixa não contam): a segunda tentativa devolve `duplicate_question`.
4. A importação em lote aceita até 500 questões e devolve três números reais: criadas, duplicadas ignoradas e erros — **cada erro identifica a questão e o motivo**, em vez de falhar o lote inteiro.
5. Toda questão nasce com o registro de estatísticas zerado; nenhum percentual é exibido antes de existir amostra.

## Classificação assistida por IA (com revisão humana)
6. A IA **sugere** disciplina, assunto, dificuldade e etiquetas; a sugestão fica guardada em `ai_suggestion` ao lado da questão.
7. Pedir a sugestão **não altera** a classificação: a questão vai para `NEEDS_REVIEW` e disciplina/dificuldade permanecem como estavam.
8. A classificação só muda quando uma pessoa aplica (`apply-classification`), e o registro guarda quem revisou e quando.
9. A sugestão declara o modelo e a versão do prompt que a produziram — a origem do texto é sempre visível.
10. A segunda solicitação para a mesma questão sai do cache: o provedor é chamado **uma única vez** (mesmo *fingerprint* de funcionalidade + modelo + versão de prompt + conteúdo).
11. O enunciado vai ao modelo dentro de `<untrusted_document>`: instruções escritas dentro da questão não viram comando.
12. Sem modelo configurado para `question.classify`, a interface diz onde configurar em vez de falhar em silêncio.

## Resolver questões
13. O candidato recebe as alternativas **sem** o campo de gabarito e sem os comentários: a correção só existe depois da resposta.
14. A correção devolve a letra certa, o comentário da alternativa marcada, o comentário da correta e a explicação geral — o candidato entende o erro, não só o placar.
15. Resposta em branco é registrada como tal (`is_blank`), não como erro comum.
16. Letra inexistente na questão é recusada (`invalid_alternative`).
17. Cada resposta atualiza os contadores agregados da questão (tentativas, acertos, tempo total).
18. **A taxa de acerto só aparece com pelo menos 20 respostas.** Abaixo disso a API devolve `accuracy: null` e a tela mostra "amostra insuficiente" — nunca um percentual construído sobre três respostas.
19. O histórico é sempre do próprio candidato: as respostas de outro usuário não aparecem.

## Simulados
20. Cada tipo tem regra própria e explícita, gravada em `config` junto com o simulado:
    - **Oficial** — mesma distribuição por disciplina do cargo do plano ativo;
    - **Da banca** — só questões da banca escolhida;
    - **Dos erros** — só o que foi errado e ainda não recuperado;
    - **Relâmpago** — até 10 questões;
    - **Personalizado** — disciplina e quantidade à escolha.
21. Quando não há dados para o tipo pedido, a resposta é `no_questions_available` **com o motivo real**: "você ainda não tem questões erradas registradas", "as disciplinas do seu plano ainda não têm questões suficientes", "não há questões cadastradas para esta banca". Nunca um simulado genérico no lugar do que foi pedido.
22. O simulado dos erros contém exatamente as questões cuja **última** resposta foi errada; questão recuperada depois sai da lista.
23. Duração em branco vira 2min30 por questão (padrão das provas objetivas); o tempo restante vem do servidor, não do relógio do navegador.
24. Uma execução em andamento por vez: iniciar outra devolve `simulation_already_running` com o identificador da atual.
25. Cada marcação é salva na hora; remarcar a mesma questão **substitui** a resposta anterior da execução.
26. Pausar congela o cronômetro e bloqueia as respostas; retomar recomeça a contagem. Pausar o que não está em andamento devolve `not_in_progress`.
27. Recarregar a página retoma exatamente de onde parou: as marcações vêm do servidor, não do navegador.
28. Encerrar produz a correção completa, calculada em Python: acertos, erros, brancos, placar, tempo médio, desempenho por disciplina, por dificuldade, pontos fracos, pontos fortes e recomendações.
29. As recomendações citam os números que as justificam; disciplina com menos de 3 questões na execução **não** entra como ponto fraco — amostra pequena não vira diagnóstico.
30. A comparação com o histórico só aparece quando existe execução anterior; no primeiro simulado, `previous_accuracy` é nulo e a tela diz "primeiro simulado".
31. A execução de um candidato não é acessível a outro (404).

## Interface
32. **Questões** — busca por enunciado, filtro por disciplina e dificuldade, resolução com correção comentada e histórico das próprias respostas.
33. **Simulados** — montagem com o tipo escolhido, o que cada tipo exige declarado antes de tentar, execução com cronômetro, grade de navegação, autosave visível e confirmação antes de encerrar informando quantas ficarão em branco.
34. **Resultado** — placar, acerto, tempo, comparação com o histórico, barras por disciplina e por dificuldade, pontos fracos/fortes e recomendações.
35. **Admin → Questões** — lista com filtro por situação, cadastro com validação do gabarito, importação JSON com o resultado detalhado e o painel de sugestão da IA com o botão de aplicar a revisão.
36. Nenhum número exibido é estimado: onde falta amostra, a tela diz que falta amostra.

## Qualidade
37. `pytest` verde (261 testes), sendo 39 da Fase 5 — 18 unitários da correção/seleção e 21 de integração (banco, prática e simulados).
38. `ruff`, `ruff format` e `mypy` sem erro no backend.
39. `tsc`, `eslint` e `vitest` (62 testes) verdes no frontend; `vite build` conclui.
40. Migração da Fase 5 cria as oito tabelas (`exams`, `questions`, `alternatives`, `question_stats`, `question_attempts`, `simulations`, `simulation_questions`, `simulation_attempts`) e reverte limpo.

## Ressalvas honestas desta entrega
- O aceite do backlog fala em "simulado oficial de 120 questões executado". O fluxo está implementado e testado ponta a ponta, mas com o banco de questões do ambiente de teste; **executar 120 questões oficiais de verdade depende de carregar uma prova real no banco** — a plataforma não gera questão oficial, e não vai inventar uma.
- **Cadernos de questões** (agrupar questões em coleções do candidato) ficaram fora desta entrega; entram junto com o Caderno de Erros da Fase 6, que compartilha a mesma estrutura.
- O simulado **adaptativo** tem a regra de dificuldade implementada e testada no domínio (`adaptive_difficulty`), mas ainda não é oferecido na interface: ele depende do Priority Score da Fase 6 para escolher *o que* perguntar, não só *quão difícil*. **Resolvido na Fase 6**: o adaptativo passou a distribuir as questões pelo Priority Score.
- As migrações foram geradas e conferidas contra SQLite (o ambiente não tem daemon Docker); a revisão para MySQL foi manual, como nas fases anteriores.

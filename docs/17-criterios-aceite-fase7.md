# Critérios de Aceite — Fase 7 (Mestre IA)

> Regra que atravessa a fase: **toda afirmação factual traz origem resolvível, e
> sem base o Mestre recusa explicitamente.** Uma resposta bonita sem origem é
> pior do que um "não sei" — porque o candidato acredita nela.

## Preparo da pergunta
1. Normalização (acento, caixa, pontuação) e expansão de siglas saem de um **dicionário**, não de um LLM: a mesma pergunta gera sempre a mesma busca, e ninguém paga token para expandir "LEP".
2. Sigla desconhecida é deixada como está — o sistema não adivinha o que ela significa.
3. O roteamento de intenção é regra explícita. Isso é deliberado: se o modelo pudesse escolher a ferramenta, poderia inventar a chamada e, com ela, um número.

## Recuperação
4. A busca combina semântica (Qdrant) e léxica (termos da pergunta) com fusão RRF, que usa a *posição* e não exige que os dois scores estejam na mesma escala.
5. O filtro de tenant é montado dentro do `VectorStore`, nunca pelo chamador — é impossível esquecer e vazar material de um candidato para outro.
6. **Sem trecho suficientemente próximo** (melhor score abaixo de 0,35), o Mestre não responde: devolve o motivo. Nunca completa de memória.
7. Base sem nada indexado não é erro: é ausência de material, e a resposta diz o que fazer (enviar e analisar o edital).
8. Sem modelo de embeddings configurado, o Mestre explica que a busca semântica está indisponível em vez de responder sem origem.
9. O orçamento de contexto nunca corta um trecho pela metade — um recorte no meio da frase quebraria a conferência literal da citação depois.

## Conferência das citações
10. O modelo devolve a resposta **quebrada em afirmações**, cada uma com seu tipo: `FACT` (exige citação), `STATISTIC` (número já calculado) ou `GUIDANCE` (orientação).
11. Cada `FACT` só é aceita se a `quote` aparecer **literalmente** no trecho recuperado, com a mesma normalização da Fase 3 e mínimo de 12 caracteres.
12. Citação que não existe no material **não some em silêncio**: a afirmação continua visível, marcada como `UNSOURCED`, com o motivo. Esconder seria decidir pelo candidato o que ele pode saber.
13. Citação curta demais não conta como prova.
14. Se **nenhuma** afirmação factual se sustentar, a resposta inteira vira recusa — mesmo que o modelo tenha respondido com convicção.
15. `STATISTIC` e `GUIDANCE` não exigem citação, e também não são apresentadas como fato sobre o edital.
16. Cada mensagem grava a fração de afirmações factuais com origem conferida (`grounding_ratio`) — é número, não impressão.

## Estatística e ferramentas
17. Todo número vem calculado do Python e é injetado no prompt dentro de `<dados_calculados>`, com instrução explícita de não recalcular.
18. Desempenho por disciplina, Priority Score e incidência da banca são anexados conforme a intenção detectada — e cada um diz quando não existe ("Priority Score ainda não calculado", "sem mapa de incidência para esta banca").
19. O contexto recuperado entra em `<contexto>` e o material do candidato em `<untrusted_document>`, com instrução de que aquilo é dado e não instrução.

## Streaming
20. `GET /tutor/conversations/{id}/ask/stream` transmite as etapas do pipeline: entender, procurar, reunir números, redigir, conferir, pronto.
21. A transmissão é **por etapa, não token a token**, e isso é uma escolha: o texto só é liberado depois que as citações são conferidas. Transmitir tokens crus exibiria afirmações que ainda podem ser descartadas por não ter origem — exatamente o que esta plataforma se recusa a fazer.
22. A etapa final informa quantas afirmações ficaram com origem conferida.
23. O stream é lido por `fetch` com o token no cabeçalho, não por `EventSource` com token na URL — token em URL vaza para histórico e log de servidor.

## Modo Professor
24. O Modo Professor usa prompt próprio e versionado, organizando a resposta em conceito, como cai na prova, onde o candidato erra e resumo.
25. Valem **todas** as regras do modo normal: citação obrigatória, estatística só do Python, recusa sem base.
26. "Como cai na prova" só aparece quando houver trecho que sustente; sem trecho, a seção é pulada em vez de preenchida por suposição.

## Vocabulário inteligente
27. Termo guardado a partir de uma resposta **herda a citação conferida** daquela mensagem e nasce marcado como `CITED`, com trecho, página e documento.
28. Termo criado à mão nasce `GENERATED` — a interface não apresenta redação de modelo como se fosse texto do edital.
29. O mesmo termo não entra duas vezes (comparação normalizada), e o vocabulário tem teto de 500 termos.

## Vídeos verificados
30. A plataforma **não descobre vídeos sozinha nem inventa links**: o catálogo é cadastrado por uma pessoa.
31. Vídeo recém-cadastrado **não é sugerido**. Só depois que alguém o marca como conferido — e o registro guarda quem conferiu e quando — o Mestre pode recomendá-lo.
32. O Mestre sugere no máximo três vídeos, sempre da disciplina da conversa.

## Conversas
33. Uma conversa pertence a quem a criou; outro candidato recebe 404.
34. O histórico recente entra no contexto do modelo, limitado a 6 turnos.
35. O título da conversa passa a ser a primeira pergunta, sem pedir que o candidato nomeie nada.
36. A recusa também fica registrada na conversa, com o motivo — o histórico mostra o que o Mestre se recusou a afirmar.

## Interface
37. **Mestre IA** — conversa com chip de origem em cada afirmação factual: verde com documento e página quando conferida, âmbar "sem origem" quando não. Clicar abre a citação ou o motivo.
38. O rodapé de cada resposta resume a cobertura ("50% das afirmações com origem conferida") e abre os trechos consultados com a proximidade de cada um.
39. As etapas do processamento aparecem ao vivo enquanto a resposta é montada.
40. Recusa é exibida como recusa, com o motivo — não como resposta vazia.
41. **Vocabulário** — cada termo mostra se veio de documento citado ou de redação da IA, e a citação de origem quando existir.
42. **Admin → Questões** ganha o catálogo de vídeos com o botão de conferir e o aviso de que o Mestre só sugere o que foi conferido.

## Qualidade
43. `pytest` verde (331 testes), sendo 33 desta fase — 20 unitários (preparo, fusão, conferência) e 13 de integração.
44. `ruff`, `ruff format` e `mypy` sem erro no backend.
45. `tsc`, `eslint` e `vitest` (85 testes) verdes no frontend; `vite build` conclui.
46. Migração da Fase 7 cria `chat_conversations`, `chat_messages`, `vocabulary_terms` e `video_resources`, e reverte limpo.

## Ressalvas honestas desta entrega
- **Streaming é por etapa, não token a token.** O wireframe pede token a token; entregar isso obrigaria a exibir texto antes da conferência das citações, contrariando a regra central da plataforma. Escolhi a regra. Se um dia houver conferência incremental, o token a token volta à mesa.
- A busca léxica é **local sobre os candidatos da busca semântica**, não um índice BM25 completo. Funciona como complemento e desempate; não substitui um índice invertido de verdade, e o documento de RAG (`docs/05-qdrant-rag.md`) descreve o alvo maior.
- **Não há rerank cross-encoder.** Ele está previsto no pipeline e a funcionalidade `rerank.default` já existe no painel, mas nenhum modelo de rerank foi integrado; a ordenação atual é score semântico + fusão RRF.
- A recuperação cobre a coleção `notices`. As coleções `legislation`, `didactic`, `questions` e `user_notes` estão desenhadas no documento de RAG e ainda não são alimentadas — o Mestre responde sobre o edital analisado, e diz isso quando a pergunta sai dessa base.
- **Ferramentas são roteadas por regra, não escolhidas pelo modelo.** É mais seguro para o princípio "Python calcula, IA redige", mas não é o *function calling* aberto que o backlog sugere. A troca está registrada aqui de propósito.
- As migrações foram geradas e conferidas contra SQLite (o ambiente não tem daemon Docker); a revisão para MySQL foi manual, como nas fases anteriores.

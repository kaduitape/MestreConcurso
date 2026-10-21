# Fase 4 (parte 1) — Geração em massa por tópico

> Quarta fase do [plano de evolução](27-evolucao-agentes-diagnostico.md). Só
> veio depois do [auditor](31-fase3-auditor.md) porque a ordem importa: gerar
> conteúdo para um edital inteiro sem portão encheria a plataforma de material
> que ninguém conferiu.

## Diagnóstico: o que já existia

1. A plataforma **já gerava** aula (Estúdio) e mapa mental, uma a uma, com
   validação de resposta, cache e medição de custo. Nada disso foi reescrito.
2. O que faltava era o **plano**: percorrer o conteúdo programático, saber o
   que já existe, dizer quanto deve custar e rodar sem repetir trabalho.
3. A Fase 1 tinha ligado conteúdo ao tópico canônico, e é esse vínculo que
   torna o reaproveitamento possível. A Fase 2 tinha passado a medir custo, e é
   essa medição que torna a estimativa honesta. Esta fase cobra as duas.

## Ninguém dispara no escuro

4. Montar o plano **não gasta um centavo**: ele lista um item por tópico e
   tipo, com a decisão escrita em cada linha.
5. A geração só começa quando **uma pessoa confirma**. A confirmação é uma rota
   separada de propósito — disparar centenas de chamadas de IA não pode ser
   efeito colateral de abrir uma tela.
6. O **agente Professor executa planos confirmados, e não confirma nenhum**. Se
   ele pudesse autorizar o próprio gasto, a confirmação não valeria nada.

## A estimativa não inventa número

7. Ela sai da **mediana do custo medido** das execuções anteriores da mesma
   funcionalidade. Mediana, não média: um estouro isolado não move o número.
8. Abaixo de três execuções medidas **não há estimativa** — a tela diz que não
   dá para estimar e sugere rodar um plano pequeno primeiro. Um chute sobre
   trezentos tópicos é como a fatura surpreende.
9. Só entra amostra que foi medida de verdade: chamada bem-sucedida, fora do
   cache e com preço cadastrado. Custo zero ali quer dizer modelo sem preço, e
   contá-lo faria a estimativa prometer barato.
10. Estimativa parcial é marcada como **incompleta**, com as funcionalidades que
    faltaram nomeadas. Somar o desconhecido como zero faria o número parecer
    completo.
11. A tela diz, com essas palavras, que estimativa não é contrato: o custo real
    de uma chamada só é conhecido depois dela.

## O que já existe não é gerado de novo

12. O vínculo é com o **tópico canônico**, que atravessa concursos: uma aula de
    "Crase" feita para um concurso já serve a qualquer outro que cobre o mesmo
    tópico. Gerar de novo seria pagar duas vezes pelo mesmo texto.
13. Rascunho conta como existente. Gerar porque o rascunho ainda não foi
    publicado é o mesmo desperdício.
14. Quando não dá para saber de onde o conteúdo veio — o mapa mental se liga ao
    tópico, não ao concurso — o motivo escrito **não inventa uma origem**.
15. O conteúdo gerado nasce com o vínculo preenchido. Sem isso, a passada
    seguinte geraria tudo de novo.

## Incremental, com teto

16. A passada roda em blocos e guarda o desfecho item a item: retomar não
    refaz o que deu certo, e uma interrupção do worker não perde trabalho pago.
17. O teto de gasto é consultado **antes de cada item**. Estourou, o item e os
    seguintes ficam `BUDGET_BLOCKED` com o motivo escrito — e uma passada
    futura tenta de novo, porque o teto pode ter mudado.
18. Falha de um item não derruba a passada: o item guarda o erro e os outros
    seguem.
19. O custo de cada item é a diferença do gasto medido — o plano não conta
    token, ele lê o que a camada de medição registrou.

## Nada é publicado aqui

20. O que sai da geração é **rascunho**. O portão da Fase 3 barra conteúdo de
    IA que nenhuma pessoa conferiu, e este serviço não tem como contornar isso.
21. Isso é o desenho, não uma limitação: a geração em massa entrega **fila de
    revisão**, e quem publica é gente.

## Qualidade

22. **15 testes de domínio** e **13 de integração**. Entre eles: que montar o
    plano não gasta token, que sem histórico não há estimativa, que o estouro
    isolado não move a mediana, que chamada em cache e modelo sem preço ficam
    de fora da amostra, que retomar não paga de novo, que o segundo plano
    reaproveita o que o primeiro gerou, e que nada sai publicado.
23. Migração `generation_plans`/`generation_items` sobe, desce e passa no
    `alembic check`.
24. A tela foi conferida em imagem renderizada.

## Defeito encontrado no caminho

25. As tarefas Celery usavam `shared_task` sem que ninguém importasse a
    aplicação configurada. A tarefa acabava ligada a uma aplicação padrão, que
    desconhece a configuração do projeto — inclusive o modo síncrono dos
    testes, que então tentavam falar com um broker inexistente. A tarefa nova
    importa a aplicação explicitamente, e a confirmação não é desfeita se o
    enfileiramento falhar: o plano fica confirmado e o agente Professor o
    executa.

## O que esta parte não entrega, e por quê

- **Flashcards (agente Memorização)**: o flashcard aqui é *pessoal de cada
  candidato*. Não existe baralho oficial por tópico — gerar em massa exigiria
  esse desenho antes, e inventá-lo de passagem seria criar um conceito novo sem
  discussão.
- **Questões (agente Mestre de batalhas)**: a plataforma **classifica** questão
  por IA, mas não **gera**. Falta a funcionalidade, com validação de gabarito e
  as regras do auditor aplicadas na origem.
- Os dois agentes continuam declarados e pulados, agora com o motivo real
  escrito na ficha deles — em vez do antigo "depende da Fase 4".

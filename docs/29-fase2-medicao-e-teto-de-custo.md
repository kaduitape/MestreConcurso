# Fase 2 (parte 1) — Medição e teto de gasto com IA

> Segunda fase do [plano de evolução](27-evolucao-agentes-diagnostico.md).
> Precede qualquer geração em massa: ligar a geração de conteúdo para um edital
> inteiro sem corte de custo é a forma mais rápida de transformar um erro em
> prejuízo.

## O defeito que esta parte conserta

A tabela `ai_usage` existia desde o começo. **Nenhum código escrevia nela.** O
painel de métricas lia dali e reportava custo de IA **zero desde sempre** — não
porque fosse zero, mas porque ninguém media.

Um teto sobre esse número seria ficção. Então a medição vem antes do teto.

## 1. Um lugar só para medir

1. Existem **nove pontos** no código que falam com um provedor de IA. Medir em
   cada um daria nove chances de esquecer, e o esquecido não aparece na conta.
2. Em vez disso, `resolve_feature` devolve o provedor **já embrulhado** por
   `app/ai/metered.py`. Quem chama continua escrevendo
   `await resolved.provider.complete(...)` e não precisa saber de nada.
3. Toda chamada passa a: ser barrada se o teto estourou → acontecer → ser
   registrada com tokens reais e custo calculado.
4. **A falha também é registrada.** Uma chamada que estourou depois de consumir
   token custou dinheiro, e some da conta se só o sucesso for contado.
5. **O registro sobrevive à falha de quem chamou.** O consumo é gravado numa
   sessão própria: se a funcionalidade der erro depois e a transação do
   chamador for desfeita, o gasto continua registrado. O token foi consumido de
   qualquer jeito.
6. Falha ao gravar o consumo **não derruba** a funcionalidade que já respondeu —
   o log é que denuncia a lacuna.

## 2. Preço ausente não vira zero

7. Modelo sem preço cadastrado grava os tokens e marca o total do mês como
   **incompleto**.
8. Somar desconhecido como zero faria o teto parecer respeitado enquanto a
   fatura cresce. É a forma mais silenciosa de o controle de custo falhar.
9. Preço pela metade (só entrada, sem saída) também é desconhecido: contar só
   um lado daria um número menor que o real, e um número menor que o real é
   pior que nenhum número.
10. O painel **diz quais modelos** estão sem preço, para a pessoa consertar o
    cadastro em vez de desconfiar do número.

## 3. O teto corta de verdade

11. Os limites vivem no banco (`ai_budgets`) e são editáveis no painel —
    **nunca no código**.
12. Zero em um limite quer dizer "sem teto para este". Há teto mensal e teto
    por execução.
13. Com o controle **desligado a medição continua**. É o que permite descobrir
    qual teto faz sentido antes de ligá-lo.
14. **O corte acontece na chamada seguinte ao estouro.** O custo de uma chamada
    só é conhecido depois dela: não há como projetar tokens de saída sem
    inventar um número. O excesso máximo é de uma chamada, e preferimos essa
    honestidade a uma estimativa fabricada. A tela diz isso em português.
15. Chamada servida pelo **cache não é barrada**, porque não gasta token.
16. Custo desconhecido não é barrado: barrar por um número que não existe
    deixaria a plataforma muda por falta de cadastro de preço — problema de
    configuração, não de orçamento.

## 4. Qualidade

17. **12 testes de domínio** e **10 de integração**. Entre eles: que toda
    chamada é registrada, que o custo sai do preço cadastrado, que modelo sem
    preço é sinalizado, que o erro do provedor é contado, que o consumo
    sobrevive à falha do chamador, e que **o teto realmente interrompe a
    chamada seguinte sem deixá-la chegar ao provedor**.
18. Migração `ai_budgets` sobe, desce e passa no `alembic check`.
19. Os dois estados do cartão foram conferidos em imagem renderizada.

## Defeito pré-existente corrigido de passagem

20. O Estúdio de Treinamento estourava com `JSONDecodeError` cru quando o
    modelo devolvia algo que não era JSON — 500 com stack trace em vez de
    recusa legível. Modelo devolvendo lixo é evento real de produção, e o
    serviço de mapas mentais já tratava isso. Agora os dois tratam.

## O que falta na Fase 2

- **O orquestrador** (`AgentRun`/`AgentStep`, dependências, tentativas,
  execução manual, progresso ao vivo) e o **registro dos oito agentes** como
  portas sobre os serviços existentes.
- Esta parte veio primeiro porque o orquestrador vai precisar perguntar
  "posso gastar?" antes de cada passo — e essa pergunta não tinha resposta.

---

# Fase 2 (parte 2) — O orquestrador

Generaliza o que o pipeline de análise de edital já fazia bem — passos
persistidos, acompanháveis ao vivo, com motivo escrito quando algo é pulado — e
acrescenta o que faltava: **dependências entre agentes, tentativas, custo por
passo e execução manual de um agente só**.

## A regra que sustenta tudo

21. **Agente que não existe nunca aparece verde.** Dois dos oito ainda não
    foram construídos (auditor e analista de melhorias) e três dependem da
    geração em massa. Eles ficam `SKIPPED` **com o motivo escrito**, nunca
    `DONE`. Um passo concluído que não fez nada é pior que um passo falho,
    porque ninguém vai investigar.
22. Os agentes são **nomes e portas** sobre serviços que já rodavam, não
    reimplementações. O orquestrador chama na ordem certa e registra.
23. **Só dois estão registrados hoje**, e ambos rodam de verdade:
    - *Analista de editais* → o pipeline de análise com suas sete etapas;
    - *Inteligência estatística* → o cálculo de incidência da banca.

    Registrar um agente vazio o deixaria verde — por isso os outros não são
    registrados.

## Dependências, tentativas e custo

24. O grafo é declarado; a ordem de execução é **derivada** dele. É o que
    permite responder quais passos podem correr juntos — o pedido pede
    paralelismo **apenas** onde não há dependência.
25. Ciclo no grafo é recusado em vez de rodar para sempre.
26. Dependência que não terminou bem faz o passo seguinte ser pulado **com a
    cadeia escrita** ("não rodou porque depende de: …").
27. Falha de um agente não derruba os independentes.
28. Tentativas são por agente e poucas: insistir num agente que falhou por
    configuração só queima tempo, e a decisão de insistir manualmente continua
    sendo de uma pessoa.
29. **Duas coisas diferentes viram "pulado", e a contagem de tentativas as
    separa:** o agente que rodou e não achou o que fazer gasta tentativa; o que
    nem existe, não.
30. O custo de cada passo é a diferença do gasto medido no período — o
    orquestrador não conta token, ele lê o que a camada de medição registrou.

## O teto encontra o orquestrador

31. O teto é perguntado **antes de cada passo**. Passo barrado fica
    `BUDGET_BLOCKED`, que não se confunde com falha de código nem com
    conclusão.
32. Execução barrada por orçamento **não conta como concluída**.

## Qualidade

33. **17 testes de domínio** e **13 de integração**. Entre eles: que o catálogo
    declara os oito, que agente sem implementação diz por quê, que pulado nunca
    vira concluído, que a cadeia de dependência aparece escrita, e que rodar um
    agente sozinho não mexe nos outros.
34. Migração `agent_runs`/`agent_steps` sobe, desce e passa no `alembic check`.

---

# Fase 2 (parte 3) — A tela, e o terceiro agente

## A tela do orquestrador

35. O acompanhamento vive no painel, aba **Agentes**. Cada estado tem cor e
    ícone próprios, e **pulado nunca se parece com concluído**: o passo pulado
    traz o motivo escrito ao lado, e o que ainda não foi construído carrega o
    selo "ainda não existe".
36. `BUDGET_BLOCKED` aparece como *Barrado pelo teto*, em dourado — separado de
    *Falhou*, em vermelho. São coisas diferentes e a tela não as mistura.
37. Enquanto a execução roda, a tela se atualiza sozinha: o estado mora no
    banco, não na memória do navegador.
38. A contagem de agentes construídos sai do próprio catálogo. Número escrito à
    mão na interface envelhece em silêncio.
39. A execução é identificada pelo **concurso e pela data**, não por um pedaço
    de identificador — é assim que uma pessoa procura o que rodou.

## O terceiro agente, e a ficha que mentia

40. O **tutor adaptativo** estava declarado como construído e não tinha
    implementação registrada. Na execução ele seria pulado dizendo "ainda não
    foi implementado", contradizendo a própria ficha dele na mesma tela.
41. Agora ele roda, sobre o Priority Score que já existia: reúne sinais reais
    do candidato e marca como ausente o sinal que não existe. **Nenhuma IA
    entra aqui** — e nenhum número é estimado.
42. Sem candidato com plano ativo para o concurso, ele é pulado com o motivo
    escrito. Ausência de insumo não é falha.
43. Um teste passou a cobrar a igualdade que faltava: **todo agente declarado
    como construído tem implementação registrada**. São três, e os cinco
    restantes dizem por que ainda não são.

## O que ainda falta

- Os agentes 3, 4 e 5 só ganham implementação na **Fase 4** (geração em massa).
- O auditor é a **Fase 3** e vem antes dela.
- O analista de melhorias continua sem desenho aprovado.

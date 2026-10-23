# Fase 4 (parte 2b) — Questões inéditas, com o gabarito conferido na origem

> Última peça da Fase 4, depois da [parte 1](32-fase4-geracao-em-massa.md) (aula
> e mapa mental) e da [parte 2a](39-fase4-parte2a-baralho-oficial.md) (baralho
> oficial). Com ela, os **oito agentes** do pedido passam a ter implementação de
> verdade.

## O que esta parte promete — e o que ela não promete

A expressão que vinha escrita na ficha do agente desde o início era "geração de
questões **com validação de gabarito**". Ela promete mais do que qualquer código
consegue, e começar pelo limite é a única forma honesta de descrever o que foi
construído.

**O que a plataforma confere sozinha, de forma determinística:**

1. a questão tem **exatamente um** gabarito;
2. o gabarito vem com uma **citação literal do material**, conferida caractere a
   caractere depois de normalizar espaços e acentos;
3. a justificativa existe, e cada alternativa errada diz por que erra;
4. as alternativas não se repetem, não estão vazias, são 4 ou 5, estão em ordem
   de letra e não incluem "todas"/"nenhuma das anteriores";
5. o enunciado tem tamanho de enunciado e não entrega a própria resposta;
6. o enunciado **não se apresenta como questão de banca**.

**O que nenhum código confere:** se o gabarito está *certo*. Um modelo pode
copiar um trecho verdadeiro do material e marcar a alternativa errada como
correta. A citação prova **respaldo declarado**, não leitura correta.

Por isso a questão gerada nasce `DRAFT` e **nenhuma chega a candidato sem
conferência humana**. O que a conferência de origem faz é jogar fora, sem custo
humano, o que já é demonstravelmente ruim — para que a revisão gaste atenção no
que só ela pode julgar. A tela diz isso com estas palavras, antes de alguém
clicar em gerar.

## Nenhuma questão gerada se passa por oficial

7. Ela nasce com `origin = AI_GENERATED` e **sem banca, sem ano e sem prova**.
   Preencher esses campos a faria passar por questão aplicada — exatamente a
   fabricação que o projeto proíbe.
8. O enunciado que **se veste** de questão de prova é descartado na origem. Três
   formas são barradas: abrir com parênteses contendo um ano (`(CESPE/2023)`,
   `[FGV 2019]` — o formato clássico de atribuição), citar uma banca conhecida
   do catálogo junto de um ano, e usar frases como "questão adaptada de prova
   anterior".
9. A lista de bancas vem do **catálogo**, não do código: uma lista fixa
   envelheceria no primeiro concurso novo. Mas a regra dos parênteses vale
   mesmo sem banca cadastrada — numa instalação nova é justamente ali que o
   enunciado com cara de prova passaria sem ninguém notar.
10. Referência normativa entre parênteses continua passando: `(Lei nº
    8.112/1990)` é citação legítima, não procedência inventada. Barrar todo
    enunciado com ano jogaria fora questão legítima sobre a Constituição de
    1988 — e descarte por coincidência é pior que não checar, porque parece
    rigor.

## O portão da Fase 3 no caminho

11. Além das conferências de forma, cada questão criada passa pelo auditor de
    conteúdo **na origem**: gabarito ambíguo, alternativa repetida e
    quase-duplicata de outra do banco já condenam a questão ali, e ela é
    apagada em vez de guardada "com aviso".
12. Uma regra do auditor fica **de fora** nesse momento, de propósito: "IA sem
    conferência humana". Ela é a razão de a questão nascer rascunho — usá-la
    para descartar jogaria fora exatamente a questão que está esperando a
    conferência que a regra exige. Há um teste para isso.
13. Na publicação, essa regra volta a valer inteira: publicar sem a marca de
    conferência humana é **barrado**. A marca é registrada por uma rota própria
    (`POST /admin/questions/{id}/reviewed`), com nome e hora.
14. Publicada, a questão **continua dizendo** que foi gerada por IA. "Oficial" e
    "gerada por IA" são informações diferentes, e nenhuma esconde a outra.

## O agente mestre de batalhas

15. Ele executa os planos de geração **já confirmados por uma pessoa**, no tipo
    `QUESTION_SET` — e não confirma plano, como o Professor e a Memorização.
16. O insumo é **aula publicada**, pela mesma razão da parte 2a: questão de IA
    escrita a partir de rascunho de IA empilharia erro sobre erro, e aqui o erro
    fica registrado como acerto ou erro do candidato.
17. Tópico sem aula publicada fica `NO_SOURCE`, com o motivo escrito e **sem
    gastar um token**.
18. Se a IA escreve e **nada passa** na conferência, o passo diz isso — com os
    motivos contados por tipo — em vez de contar como sucesso o que não produziu
    nada. É o mesmo estado `NO_SOURCE`, cujo significado foi escrito por
    extenso: não havia insumo utilizável, seja por falta de aula, seja porque
    nada que saiu dela se sustentou.
19. **Cobertura conta.** Para questão, "já existe conteúdo" não é sim ou não: é
    quantas. Um tópico com dez questões no banco não precisa de questão gerada;
    um com duas, precisa. O corte (`min_questions_per_topic`) é escolha de quem
    monta o plano, não constante de código, e o motivo do item diz o número:
    *"Já existe conteúdo para este tópico: 7 questão(ões) no banco."*

## O simulado passou a declarar sua composição

20. Questão gerada e publicada entra no banco como qualquer outra — e o simulado
    é lido pelo candidato como **imitação da prova**. Treinar com questão de IA é
    legítimo; não saber que se está treinando com ela, não é.
21. A execução do simulado agora devolve a **composição por procedência**,
    derivada dos itens, e a tela mostra o selo em cada questão mais uma linha no
    começo: *"Este simulado tem 3 questão(ões) gerada(s) por IA entre as 40"*.
22. Era uma lacuna anterior a esta parte: a tela de batalha já mostrava
    procedência, a do simulado não.

## Como conferir

```bash
# As conferências de origem, uma a uma
pytest tests/unit/test_question_generation_domain.py -q

# Ponta a ponta: rascunho sem banca, descarte com motivo, portão da publicação
pytest tests/integration/test_question_generation.py -q

# O agente: aula publicada, nada aprovado, tópico já coberto
pytest tests/integration/test_agent_battle_master.py -q
```

No painel: **Administração → Questões → Gerar por IA**. A conferência humana da
questão gerada fica no detalhe dela, no mesmo lugar onde a citação do gabarito é
mostrada.

### O que foi verificado

| Verificação | Resultado |
|---|---|
| Backend | suíte completa verde |
| `ruff check` / `ruff format` | limpos |
| `mypy` nos arquivos desta parte | limpo |
| Frontend | `npm run lint`, `npm run typecheck` e `vitest` verdes |
| Migração | **nenhuma**: o modelo de questão já tinha `AI_GENERATED`, `DRAFT` e os campos de revisão |

## Os testes do orquestrador ficaram sem exemplo

24. Dois testes usavam "um agente não construído" como exemplo, e o exemplo
    mudou três vezes conforme os agentes foram sendo feitos (melhorias →
    memorização → mestre de batalhas). Agora não há mais nenhum.
25. A regra que eles protegem continua valendo para o próximo agente que for
    declarado antes de existir, então eles não foram apagados — foram
    reescritos para exercitá-la sem depender de um agente real: o de domínio usa
    uma ficha sintética, e o de integração **retira do registro** a
    implementação de um agente e confere que o passo sai *pulado com motivo*, em
    vez de verde.
26. Entraram dois testes novos no lugar do exemplo perdido: nenhum agente pode
    ficar declarado sem motivo escrito, e os oito do pedido precisam ter
    implementação registrada — catálogo e registro contando a mesma história.

## Um defeito encontrado no caminho

23. A primeira versão da regra "o enunciado entrega a resposta" comparava o texto
    da alternativa correta com o enunciado caractere a caractere. Um **ponto
    final** a mais na alternativa derrubava a comparação, e a regra não pegava
    nada. Agora a pontuação das pontas é ignorada — e alternativa curta ("Dez
    dias") não conta como entrega, porque coincidência de palavra curta
    descartaria questão legítima.

## O que esta parte não entrega

- **Questão discursiva e certo/errado.** O gerador escreve múltipla escolha. As
  outras formas têm regras próprias de gabarito, e tratá-las de passagem seria
  esticar a palavra "validação" além do que o código faz.
- **Geração a partir de trecho de edital.** Vale aqui o mesmo da parte 2a: a
  procedência existe no modelo, mas nenhum caminho automático a usa ainda.
- **Revisão em lote.** A conferência humana é uma por questão, de propósito:
  marcar vinte de uma vez transformaria a marca num clique sem leitura, e é
  justamente a leitura que ela registra.
- **Estatística separada por procedência.** O simulado declara a composição, mas
  o desempenho do candidato ainda não é quebrado entre questão de prova e questão
  gerada. É medição nova, e merece desenho próprio.

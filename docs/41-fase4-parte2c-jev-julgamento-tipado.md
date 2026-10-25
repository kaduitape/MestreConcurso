# Fase 4 (parte 2c) — O JEV entra, e o que ele realmente é

> O item 15 do plano — *"adaptador `DecisionProvider` para o JEV, **com a
> documentação em mãos**"* — esteve bloqueado desde a
> [Fase 6](34-fase6-roteador.md) por falta da referência da API. A documentação
> chegou por um caminho que ninguém previa, e com ela veio a descoberta de que a
> premissa do pedido original estava errada.

## Como a documentação chegou

1. O JEV não é um serviço que se descobre pelo site: a entrada é uma **skill de
   agente** publicada em `typesafe-ai/skills`, instalável como plugin do Claude
   Code. Ela não é o produto — é o guia que diz onde está a documentação viva e
   como desenhar com as primitivas.
2. `docs.typesafe.ai` **continua recusado** pela política de rede deste
   ambiente, e `api.typesafe.ai` também. Mas a própria skill prevê esse caso e
   nomeia a alternativa legítima: *"se o acesso ao vivo não estiver disponível,
   use a documentação local ou os **tipos do SDK instalado**, declare a
   limitação e não invente detalhes que dependem de versão"*.
3. Foi o que se fez. O contrato desta parte saiu do **`typesafe-sdk` 0.7.5**
   instalado — assinaturas, modelos de resposta, nomes de variável de ambiente e
   taxonomia de erro —, não de suposição. O que **não** foi feito: nenhuma
   chamada real contra o serviço, porque o host está bloqueado. Isso está
   declarado também no fim deste documento.

## O que o JEV é, e o que ele não é

4. Ele recebe **estado da aplicação** e **perguntas com tipo de resposta
   declarado**, e devolve **respostas tipadas com probabilidade**. Não gera
   texto, não explica o raciocínio.
5. Três primitivas: `Choice` (uma de um conjunto, com distribuição), `Noul`
   (probabilidade de uma condição valer, sem confiança separada) e `Score`
   (posição numa escala de níveis descritos).
6. **Ele não orquestra, não escolhe modelo e não pesquisa.** A documentação é
   explícita: *"o código é dono do fluxo"*. A advertência que estava no
   diagnóstico da Fase 6 — *"não presumir que o JEV tem orquestração, escolha
   automática de modelos ou pesquisa externa"* — se confirmou inteira. O item 15
   nunca foi um roteador; é um **provedor de julgamento**.

## A porta é nova, e isso é deliberado

7. `AIProvider` é moldado em texto: `complete`, `embed`, `synthesize_speech`.
   Um modelo que devolve "qual das cinco, com distribuição" não cabe ali sem que
   alguém volte a fazer *prompt-and-parse* — exatamente o que esta camada existe
   para eliminar. Então entrou uma porta **paralela**, `DecisionProvider`
   (`app/ai/decisions.py`), com perguntas e vereditos neutros de fornecedor.
8. O que foi **reaproveitado**, de propósito: credencial, medição (`Usage`),
   teste de conexão, ficha de modelo e a família `ProviderError`. Duas
   taxonomias de erro para dois fornecedores de IA seria o começo de duas
   plataformas.
9. O adaptador (`app/ai/providers/typesafe.py`) é o **único** arquivo que fala
   SDK. Ele traduz nos dois sentidos e nada mais. Diferente dos outros
   adaptadores, usa o SDK em vez de HTTP cru: reimplementar à mão a serialização
   de primitivas com distribuição seria assumir um formato de fio que o
   fornecedor pode mudar sem avisar.
10. O medidor da Fase 2 ganhou um irmão (`MeteredDecisionProvider`) no mesmo
    arquivo. Medir em dois lugares daria duas chances de esquecer, e o esquecido
    não aparece na conta.
11. O roteador da Fase 6 **ignora** a funcionalidade de julgamento, e o motivo
    está escrito ao lado dos outros dois: não há reserva equivalente para
    desviar, e as probabilidades de dois modelos diferentes não são comparáveis
    entre si.

## O primeiro uso: o buraco que a parte 2b declarou

Na [parte 2b](40-fase4-parte2b-geracao-de-questoes.md) ficou escrito:

> *"O que nenhum código confere: se o gabarito está certo. A citação prova
> respaldo declarado, não leitura correta."*

12. É esse buraco que esta parte cobre — parcialmente, e com o limite dito. Um
    `Noul` pergunta: **a citação do material sustenta que a alternativa marcada
    é a correta?** A resposta é uma probabilidade calibrada.
13. O estado enviado é só o necessário: enunciado, a alternativa marcada, as
    erradas e o trecho citado. O material inteiro não vai — a pergunta não é "o
    material fala disso?", e estado maior é token pago sem resposta melhor.
14. **A probabilidade não publica nada.** Ela serve para duas coisas: ordenar a
    fila de revisão humana (respaldo mais fraco primeiro, onde a leitura rende
    mais) e, se o administrador quiser, barrar o pior na origem.

### O piso é escolha de quem administra, e o padrão é zero

15. Qualquer número embutido por mim aqui seria uma régua inventada decidindo o
    que vai para o lixo. Uma probabilidade de modelo só ganha significado depois
    de alguém comparar as decisões dele com as de uma pessoa **nos dados reais
    desta plataforma**.
16. Então o piso padrão é **zero**: o julgamento ordena a fila e não descarta
    nada. Quem quiser barrar sobe o piso no painel, sabendo o que escolheu — e
    aí o descarte aparece com o número: *"o julgamento do gabarito ficou em 19%,
    abaixo do piso de 50%"*.

### "Não conferido" não é zero e não é aprovação

17. A coluna `questions.answer_key_support` é **anulável**, e nulo quer dizer
    não conferido: funcionalidade desligada, provedor recusado, chamada falhada,
    ou questão que não veio de geração.
18. A tela diz isso com estas palavras, no diálogo de geração e no detalhe da
    questão. Na fila ordenada, a não conferida aparece **no fim** — ela não tem
    número, e pôr "sem informação" no topo faria parecer "informação ruim".
19. Falha no julgamento no meio de uma passada **não derruba a geração**: as
    questões que faltaram ficam não conferidas e o motivo é dito **uma vez**, em
    vez de repetido por questão.

## Um defeito de concorrência que o SQLite expôs

20. A primeira versão perguntava ao Jev **dentro** da transação da requisição,
    logo depois de gravar o rascunho. A medição grava em sessão própria (para
    sobreviver a rollback, desde a Fase 2), e as duas se trancaram: *database is
    locked*.
21. O conserto não foi de banco, foi de desenho: a geração passou a ter **duas
    fases**. Primeiro gravar e auditar, com a transação fechada no fim; depois
    julgar, uma questão por vez, cada desfecho confirmado na hora. Se a passada
    morrer no meio, o que foi julgado fica julgado e o resto fica não conferido —
    que é verdade.
22. E isso não é detalhe de SQLite: segurar uma linha travada durante uma
    chamada externa de dez segundos é ruim em qualquer banco.

## Outro defeito, do mesmo tipo, que vinha de trás — e o conserto que falhou

23. `AIBudgetService.guard()` consultava o teto por um caminho que **inseria** a
    linha de configuração quando ela não existia. A Fase 6 já tinha corrigido
    isso uma vez, para o roteador, com `month_spend_and_limit()`; o `guard`
    ficou de fora e o defeito reapareceu por um caminho novo.
24. O primeiro conserto fez o `guard` ler sem criar — e **quebrou outro teste**,
    o do analista de melhorias. Vale registrar por quê, porque o erro foi meu e
    é instrutivo: a inserção escondida não desapareceu, ela só **mudou de
    lugar**. Antes, o `guard` criava a linha e o commit do passo a fechava;
    depois, quem criava era `overview()`, chamado logo adiante, **dentro** da
    transação aberta do passo do orquestrador — e aí o analista, que grava em
    sessão própria, encontrava o banco trancado.
25. O conserto certo foi tratar a família inteira: **nenhum** caminho de leitura
    cria a linha. `limits()` e `overview()` leem; quem cria é `set_limits()`,
    que é quem de fato grava. Linha ausente significa **sem teto configurado**,
    que é o padrão da tabela.
26. A regra, escrita desde a Fase 6 e agora valendo sem exceção: **ler não pode
    escrever**.

## Como conferir

```bash
# O adaptador, contra o contrato real do SDK e sem rede
pytest tests/unit/test_typesafe_adapter.py -q

# A regra do piso e o "não conferido"
pytest tests/unit/test_question_generation_domain.py -q -k "support or floor or checked"

# Ponta a ponta: desligado, ligado, piso, falha e medição
pytest tests/integration/test_answer_key_support.py -q
```

No painel: **Administração → Inteligência**, provedor `typesafe` e a
funcionalidade *Conferência do gabarito (julgamento tipado)*. A fila de revisão
fica em **Questões → ordenação "Fila de revisão"**.

### O que foi verificado

| Verificação | Resultado |
|---|---|
| Tradução pergunta ↔ primitiva, resposta ↔ veredito | 8 testes contra os tipos do SDK, com transporte injetado |
| Erros do SDK → família `ProviderError` | 401/403/429 e tempo esgotado conferidos |
| Fluxo completo (desligado, ligado, piso, falha, medição) | 6 testes de integração |
| Migração `d58c2b4f91ac` | up / down / up em SQLite, `alembic check` limpo |
| Backend | suíte completa verde |
| Frontend | `lint`, `typecheck` e `vitest` verdes |
| `mypy` | 36 erros pré-existentes, nenhum novo |
| **Chamada real contra `api.typesafe.ai`** | **não feita** — host recusado pela política de rede |

## O que falta para isto valer em produção

25. **Liberar `api.typesafe.ai`** na política de rede do ambiente e na saída da
    VPS. Sem isso, a funcionalidade fica desligada e toda questão nasce não
    conferida — que é o comportamento correto, mas é só metade do que esta parte
    construiu.
26. **A chave**, cadastrada no painel como as outras: criptografada no servidor,
    nunca no navegador. A variável `TYPESAFE_API_KEY` existe no SDK, mas aqui a
    chave vem do banco, como a dos demais provedores.
27. **Liberar `docs.typesafe.ai`** seria útil para a próxima parte: os cookbooks
    de *citation check* e *hierarchical classification* provavelmente mostram uma
    decomposição melhor do que a que eu desenhei com uma pergunta só.

## O que esta parte não entrega

- **Calibração.** Ninguém mediu ainda se a probabilidade do Jev concorda com a
  revisão humana **nesta** plataforma. Até isso acontecer, o número ordena a
  fila e não decide descarte — e é por isso que o piso padrão é zero.
- **Os outros usos do julgamento tipado.** Vínculo tópico ↔ catálogo,
  classificação de questão, causa do erro e reordenação para o tutor são
  candidatos naturais e ficaram de fora de propósito: cada um troca uma chamada
  de LLM existente, e trocar quatro de uma vez impediria de saber qual melhorou.
- **Julgamento no baralho oficial.** O cartão tem o mesmo problema de gabarito
  que a questão. Entra depois, quando houver calibração para comparar.

---

> **Próxima parte:** [cadastro de concurso a partir do edital](42-cadastro-de-concurso-pelo-edital.md)
> — sobe o PDF e o concurso sai cadastrado, com o que o edital sustenta por
> citação conferida e com o que faltou dito item por item.

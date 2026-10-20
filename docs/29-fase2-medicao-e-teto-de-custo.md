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

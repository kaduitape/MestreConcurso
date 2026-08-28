# Critérios de Aceite — Fase 10 (Comercial)

> **Aceite do backlog:** ciclo completo **assinar → cobrar → limitar → cancelar**,
> com os limites vindos do banco. E a regra do projeto que governa a fase:
> **os recursos e limites não podem ficar hardcoded.**

## Planos e direitos de uso
1. O código define apenas a *forma* de um direito e o catálogo de fábrica que semeia a tabela na primeira subida. Depois disso quem manda é `plan_entitlements`.
2. Mudar preço, limite ou acesso é um `UPDATE` pela API de administração — **sem deploy**. Há teste que altera o teto e confirma que o bloqueio muda junto.
3. **"Sem acesso" e "sem teto" são campos separados** (`is_enabled` e `limit_value`). Guardar os dois em um só é como sistemas de cobrança liberam recurso pago por engano.
4. Todo direito se descreve em texto legível, e o plano exibe **também o que não concede** — esconder o excluído é a forma educada de mentir num pricing.
5. Só entram como recurso comercial ações que o **candidato executa**. Análise de edital e classificação de questões são administrativas; colocá-las num plano criaria um limite que nunca se aplica.
6. **Nenhum conteúdo de estudo fica atrás do pagamento** (itens 3 e 24 do pedido): no plano gratuito, simulados, desafios e Analytics são limitados, nunca bloqueados.
7. Quem não assinou cai no plano gratuito — "sem assinatura" tem direitos definidos, em vez de virar condicional espalhada pelo sistema.
8. Recurso desconhecido é **negado**, nunca liberado por omissão.

## Assinar
9. Contratar um plano pago **não libera o acesso pago**: a assinatura nasce em teste (quando há) ou pendente de pagamento. Quem libera é a confirmação do adquirente.
10. Uma segunda assinatura é recusada com o caminho: use a troca de plano.
11. Cupom inválido devolve **o motivo** — expirado (com a data), esgotado, de outro plano, já usado ou abaixo do valor mínimo.
12. O desconto nunca ultrapassa o valor cobrado: cupom não vira crédito nem valor negativo.
13. Toda recusa de cupom devolve o valor original intacto.
14. O período de cobrança respeita o fim do mês: quem assina em 31 de janeiro renova em 28 de fevereiro, não em 3 de março.

## Cobrar
15. A credencial do adquirente é **cifrada** no banco (mesmo mecanismo da chave de IA da Fase 2) e **nunca volta pela API** — só a dica visual.
16. Sem provedor configurado, o checkout é recusado com `payment_not_configured` e o motivo.
17. **A assinatura do webhook é verificada** no formato documentado pelo provedor (`ts=…,v1=…` sobre o manifesto `id:…;request-id:…;ts:…;`), com `compare_digest` e janela de tolerância de tempo contra reenvio antigo.
18. Notificação sem assinatura, com assinatura forjada ou fora da janela é **recusada** — e não vira linha nem processamento.
19. **O corpo do webhook nunca é a verdade.** Ele traz um identificador; o status vem de uma consulta à API com a credencial da conta. Aceitar o corpo permitiria a qualquer um que descubra a URL declarar um pagamento aprovado.
20. **Reenvio não credita duas vezes**: cada notificação é única por (provedor, id do evento), e a segunda chegada responde `duplicate`.
21. Notificação de tópico não tratado é registrada e ignorada, com o motivo.
22. O webhook responde 200 mesmo ao recusar: repetir indefinidamente uma notificação inválida não ajuda ninguém, e o motivo fica no log.
23. Pagamento aprovado renova o período, emite a linha de faturamento e registra o resgate do cupom — uma vez só.
24. Pagamento recusado **não corta o acesso na hora**: abre a tolerância declarada, porque cartão recusado é quase sempre problema de banco, não decisão de quem estuda.

## Limitar
25. O limite é verificado **antes** de gastar: chamada recusada não faz o contador subir.
26. A recusa por limite diz **três coisas**: quanto foi usado, qual é o teto e o que fazer (esperar a virada, com a data, ou mudar de plano).
27. A janela mensal segue o **aniversário da assinatura**, não o mês civil: quem assina dia 20 tem o contador zerado todo dia 20.
28. A janela é gravada na linha do contador: virou a janela, é outra linha — o contador não depende de "que dia é hoje" na leitura.
29. Recurso ilimitado **não cria contador**: a linha só existiria para crescer sem nunca ser lida.
30. Recurso fora do plano devolve `feature_not_included` com o caminho; recurso no teto devolve `quota_exceeded` com os números.
31. Analytics é porta **booleana**, sem contador: cobrar uma unidade por abrir tela contraria o pedido de não pontuar tela aberta.

## Trocar e cancelar
32. **Upgrade vale na hora**, com crédito proporcional aos dias já pagos — cobrar o plano novo sem descontar seria cobrar duas vezes pelos mesmos dias.
33. **Downgrade vale no fim do período**: quem pagou o mês inteiro tem o mês inteiro, sem cobrança nova nem devolução.
34. Trocar para o mesmo plano é recusado, e não processado silenciosamente.
35. **Cancelar não corta na hora.** Quem pagou até o dia 30 tem acesso até o dia 30; o estado é `CANCELING` e a tela diz isso.
36. Todo movimento vira linha em `subscription_events` — quando alguém perguntar "por que meu acesso mudou?", a resposta existe.

## Painel de SaaS
37. MRR, ARPU, churn, custo de IA e margem, **cada um com o denominador escrito**.
38. Plano anual entra pelo duodécimo, truncado para baixo: arredondar para cima superestimaria receita.
39. **Churn exige período encerrado** e base não vazia. No meio do mês seria meia informação com cara de indicador.
40. Indicador sem base é `None` **com motivo**, nunca zero.
41. O painel exige permissão (`billing:read`); um candidato recebe 403.

## Qualidade
42. Domínio puro, sem I/O: nada em `app/domain/billing/` importa banco, HTTP ou provedor.
43. A integração com o adquirente fica atrás de uma **porta** (`PaymentProvider`), como a porta de IA da Fase 2 — trocar de adquirente é implementação nova, não reescrita.
44. Cobertura: 43 testes de domínio, 23 de integração e 9 de componentes React, todos verdes.
45. `ruff`, `mypy`, `eslint`, `tsc` e `prettier` limpos nos arquivos da fase.
46. A migração sobe e desce sem erro, e `alembic check` não detecta desvio.

## O que esta fase **não** entrega
47. **A integração com o Mercado Pago não foi exercida contra a API real.** O cliente HTTP segue a documentação do provedor e é testado pela porta, com o serviço verificado ponta a ponta; a verificação de assinatura segue o manifesto documentado. Antes de produção é obrigatório um teste em *sandbox* com credencial real: criação de preferência, retorno das `back_urls` e uma notificação verdadeira.
48. Não há cobrança recorrente automática (assinatura no adquirente): cada período gera uma cobrança avulsa. Recorrência é trabalho seguinte.
49. Não há emissão fiscal. `invoice_lines` é o registro do que foi cobrado, não uma nota fiscal.

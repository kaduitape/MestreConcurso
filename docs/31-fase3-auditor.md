# Fase 3 — O auditor, antes de qualquer geração em massa

> Terceira fase do [plano de evolução](27-evolucao-agentes-diagnostico.md).
> Vem **antes** da Fase 4 de propósito: ligar a geração de conteúdo para um
> edital inteiro sem portão é a forma mais rápida de encher a plataforma de
> material que ninguém conferiu.

## Diagnóstico: o que já existia

1. O banco de questões **já validava na porta de entrada**: pelo menos duas
   alternativas, exatamente uma correta, letras sem repetição, e um checksum do
   enunciado que barra duplicata exata. Isso não foi reescrito.
2. O que faltava não era validação de formulário — era **portão de
   publicação**. Cada caminho tinha a sua checagem solta ("mapa sem painel",
   "aula sem cena") e nenhum deles deixava registro.
3. E faltava o que nenhuma validação cobria: **texto de alternativa repetido**
   (a letra era conferida, o texto não), tópico fora do edital, e conteúdo de
   IA publicado sem conferência humana.

## A regra que sustenta a fase

4. **Nenhuma IA no auditor.** Um auditor que julga por modelo de linguagem não
   repete o mesmo veredito sobre a mesma questão, não mostra a conta e cobra
   token para dizer "parece bom". Cada regra aqui é uma função pura com nome,
   limiar e evidência escrita — dá para discordar dela, e dá para desligá-la.
5. Três severidades, e a terceira é a que falta na maioria dos sistemas:
   - **Bloqueia** — defeito objetivo, impede a publicação;
   - **Avisa** — suspeita que precisa de olho humano;
   - **Não conferido** — *o que não deu para julgar*. Sem edital analisado não
     dá para dizer se o tópico está no programa; silenciar isso faria o laudo
     limpo parecer uma aprovação que ninguém deu.
6. O veredito é **derivado das marcas**, nunca acumulado.

## As dez regras

7. Questão: sem gabarito, mais de um gabarito, alternativa repetida,
   alternativa vazia, enunciado curto demais, questão quase igual a outra.
8. Qualquer conteúdo: tópico fora do edital, conteúdo sem vínculo com o
   catálogo, gerado por IA sem conferência humana, corpo vazio (aula sem cena,
   mapa sem painel).
9. **Nenhuma delas mora no código como valor fixo.** Severidade, limiares e o
   liga-desliga vivem em `content_audit_rules`; o código traz só o padrão, e a
   tabela vence. Desligar uma regra é a saída honesta quando ela está errada —
   e fica registrado em quem desligou.
10. "Quase igual" é aviso, não bloqueio: pode ser variação legítima. O laudo
    nomeia a outra questão e a nota da comparação.

## O portão fecha as quatro portas

11. Questão **nasce publicada** neste sistema, então o portão está na criação,
    não só na revisão. Também na **edição que promove** o rascunho, na
    aplicação da classificação e em cada linha de uma **importação** que entre
    publicada.
12. Aula e mapa passam pelo portão na publicação.
13. Rascunho não é barrado: o portão é de publicação, e trabalho em andamento
    precisa poder ser salvo quebrado.
14. Na criação e na importação o laudo **não** é gravado: o conteúdo recusado
    não chega a existir, e um laudo apontando para o nada só sujaria o
    histórico. O motivo da recusa vai na resposta.

## O laudo sobrevive à recusa

15. Quando o portão barra, a transação de quem tentou publicar é desfeita. Se o
    laudo morasse nela, o histórico perderia exatamente as linhas que explicam
    as recusas — então ele é gravado **numa sessão própria**, pelo mesmo motivo
    que o consumo de IA já era.
16. Cada conferência é uma linha nova. **Nada é sobrescrito:** o histórico de
    correções é a sequência de laudos do mesmo conteúdo, com o defeito
    aparecendo numa linha e sumindo na seguinte.
17. O laudo guarda o **alcance** da conferência — quantas questões entraram na
    comparação de duplicata, quantos tópicos o edital trouxe. Sem isso, "nada
    encontrado" viraria uma garantia que o auditor não deu.

## O agente auditor

18. O sétimo agente saiu do papel. Ele varre o conteúdo **publicado** do
    concurso — e publicado de propósito: o rascunho ainda vai passar pelo
    portão, o que o auditor precisa vasculhar é o que já chegou a quem estuda.
19. Ele **deixou de depender** da geração em massa. Nasceu declarado como
    dependente dos agentes de memorização e batalha; amarrá-lo a agentes que
    ainda não existem deixaria o portão de qualidade parado esperando a Fase 4.
20. Sem edital analisado, a varredura diz o que ficou de fora em vez de
    devolver um relatório limpo.

## Qualidade

21. **20 testes de domínio** e **14 de integração**, além dos ajustes no
    orquestrador. Entre eles: que o laudo sobrevive à recusa, que o histórico
    mostra o defeito sumindo, que a regra desligada deixa a publicação passar,
    que severidade "não conferido" não é configurável, e que rascunho não é
    barrado.
22. Migração `content_audits`/`content_audit_rules` sobe, desce e passa no
    `alembic check`.
23. A tela foi conferida em imagem: regra desligada aparece em vermelho
    tracejado, e "não conferido" tem cor e ícone próprios.

## O que esta fase não entrega

- **Julgamento tipado por JEV** (item 10 do plano) continua fora: a integração
  segue bloqueada por falta da referência da API.
- **Edição de alternativas pela API** não existe — dá para criar e listar, não
  para corrigir uma alternativa errada sem recriar a questão. O auditor
  *encontra* o defeito que a plataforma ainda não deixa consertar pela tela.
  Fica anotado como lacuna conhecida, não resolvida aqui.

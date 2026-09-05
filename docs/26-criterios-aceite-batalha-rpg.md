# Critérios de Aceite — Batalha RPG (Fases 1 e 2)

> **Regra que governa esta entrega:** é um RPG 2D por cima de uma plataforma
> séria de concurso. O combate é a **consequência visual** da resposta, nunca a
> fonte dela. Se a animação e a questão disputarem a tela, a questão ganha.

Escopo da **Fase 1**: os dois modelos de tela, a seleção automática entre eles, o
guerreiro, os monstros, as barras de vida, a pergunta, as respostas, acerto,
erro, ataque, dano, explicação e responsividade.

Escopo da **Fase 2**: XP, combo, moedas, poderes, sons e críticos.

**Chefes, campanhas, equipamentos, classes e ranking são Fase 3** e não foram
implementados.

## Reaproveitamento
1. A batalha **não é um sistema paralelo**. É o modo `BATTLE` de `GameRun`: mesma
   largada, mesma lista de questões congelada, mesma rota de resposta
   (`ChallengeService.answer` → `QuestionAttempt`), mesmo XP, mesmas missões,
   mesmo histórico e mesmos limites de plano. Só a apresentação é nova.
2. Autenticação, banco, questões, tema, `GameButton`, `GameCard`,
   `ProvenanceBadge` e o personagem do Dia de Treinamento vêm do que já existia.
   Nenhum deles foi recriado.

## Combate
3. **A vida não é guardada em lugar nenhum.** `evaluate_battle()` recalcula as
   duas barras a partir das respostas da rodada, a cada leitura. Um contador
   paralelo poderia divergir do que a pessoa realmente respondeu — e aí o
   combate estaria mentindo sobre o estudo.
4. Acerto: o guerreiro ataca e o monstro perde vida. Erro: **o monstro da
   alternativa correta** contra-ataca e o guerreiro perde vida.
5. O erro custa menos do que o acerto rende (20 contra 34): a batalha termina
   por acerto, não por desistência.
6. A vida do monstro **atravessa as questões** da rodada — é uma batalha, não
   oito duelos independentes.
7. A vida máxima do monstro sai do número de questões e da taxa-alvo de acerto
   (`ENEMY_HP_ACCURACY_TARGET`), não de um número escolhido a dedo.
8. Vitória exige **derrubar o monstro**. Acabar as questões com ele de pé não é
   vitória, e a tela diz isso com todas as letras.
9. A tela **nunca calcula dano sozinha**. Quem responde quanto foi tirado é o
   servidor; o cliente só anima o que recebeu.
10. O número da barra muda **no impacto**, junto com o efeito — não meio segundo
    antes dele.

## Layouts
11. Existem dois modelos, e só dois: `monster-arena` (alternativa curta, um
    monstro grande por alternativa) e `compact-answer` (alternativa longa,
    avatar pequeno ao lado do texto inteiro).
12. A escolha é automática e olha **as alternativas**, não o enunciado: número de
    alternativas, maior alternativa, média e linhas estimadas. Cada decisão
    devolve o motivo por escrito.
13. **Os limiares não são fixos no código.** Ficam na tabela `battle_settings`,
    semeados a partir do padrão de fábrica e editáveis no painel administrativo,
    com auditoria. Mudar o número muda a decisão na questão seguinte, sem deploy.
14. Celular, tablet e desktop têm limiares próprios: o mesmo conjunto de
    alternativas pode ir para a arena no desktop e para o compacto no celular.
15. A conta é refeita no cliente com a largura real da tela, usando **as mesmas
    réguas** que vieram do banco. O servidor sugere; quem mede é o navegador.
16. **O layout congela quando a questão aparece** e só muda na próxima. Girar o
    telefone no meio da leitura não empurra o texto para debaixo do dedo de quem
    está respondendo.
17. No modelo compacto o texto tem prioridade absoluta: não encolhe, não corta,
    e **nada que se move carrega texto junto** — na hora do golpe mexem só o
    avatar, a borda e o efeito.
18. No modelo arena, **toda a região da alternativa é o botão** (monstro, letra e
    texto). Alvo grande importa mais no celular do que qualquer efeito.

## Estado e animação
19. A tela é dirigida por uma **máquina de estados** (`battleReducer`), não por
    booleanos espalhados. Evento fora de ordem é ignorado em vez de pular etapa.
20. Falha de rede dispara `FAILED`: o controle volta para a pessoa. A tela nunca
    fica presa em "atacando".
21. Escolhida uma alternativa, as outras travam na hora — o segundo clique não
    troca a resposta já enviada.
22. Só quatro estados de animação por personagem: `idle`, `attack`, `hurt`,
    `dead`. Nada de ciclo de caminhada, partículas ou física.
23. Só `transform` e `opacity` são animados, com `will-change: transform`. São as
    propriedades que o navegador resolve na placa de vídeo, sem recalcular
    layout a cada quadro.
24. Com **"reduzir animações"** ligado no sistema, a linha do tempo cai para o
    mínimo, o efeito de espada não é renderizado e nada pisca. O jogo continua
    jogável.
25. `BattleEngine` (regra) e `BattleRenderer` (desenho) são separados:
    `domain/game/battle.py` é puro e não sabe que existe tela; os componentes não
    sabem calcular vida.

## Arte e peso
26. Os monstros são **SVG inline**, não sprites baixados: nada a esperar antes da
    primeira questão, escala sem borrar e cor vinda dos tokens do tema. O campo
    `shape` permite trocar por arte WebP depois sem tocar no resto.
27. A identidade do monstro é **determinística** (hash do identificador): o mesmo
    inimigo do começo ao fim da rodada, sem persistir nada.
28. O guerreiro reaproveita o personagem que o produto já tinha. Não há uma
    segunda arte para a mesma pessoa dentro da plataforma.
29. Nada de 3D, Unity, Unreal, motor de física ou biblioteca nova. Framer Motion
    e Tailwind, que já estavam no projeto.

## Leitura e honestidade
30. O enunciado tem painel próprio, **sem animação de entrada**, e rola quando
    precisa. A questão é o motivo de a pessoa estar ali.
31. A procedência da questão (OFICIAL / GERADO POR IA / HISTÓRICO) aparece dentro
    da batalha. Combate não é motivo para embaralhar origem de conteúdo.
32. A explicação só aparece quando pedida, e é estática: leitura interrompida por
    animação não é lida.
33. Questão sem explicação cadastrada **diz que não tem**. Nada é gerado para
    preencher o espaço.
34. O fim da batalha fala da batalha e do desempenho medido. **Nenhum texto
    afirma, sugere ou insinua aprovação** (item 40 da gamificação).
35. As barras de vida são `progressbar` com valor, mínimo e máximo; os monstros
    têm nome acessível; a saída da batalha fica sempre visível.
36. A rodada abandonada não pontua, como qualquer outra rodada de desafio.

## Qualidade
37. `domain/game/battle.py` é puro: sem banco, sem HTTP, sem IA.
38. 26 testes de domínio, 17 de integração e 21 no cliente cobrem layout,
    combate, bestiário, réguas vindas do banco, máquina de estados e os dois
    modelos de tela.
39. Migração `battle_settings` sobe e desce limpa; `alembic check` sem
    divergência.
40. Fases 2 e 3 (XP de combate, combo, moedas, poderes, som, chefes, evolução)
    **não foram implementadas**, por decisão explícita: a Fase 1 precisa estar
    estável antes.

---

# Fase 2 — combo, crítico, moedas, poderes, som e XP

> **Regra que governa esta fase:** o que a Fase 2 acrescenta continua sendo
> **derivado das respostas**. Combo, crítico, dano e saldo saem da mesma conta
> que já desenhava o HP. Nada é sorteado — porque o que é sorteado não pode ser
> reconstruído, e o que não pode ser reconstruído precisa ser guardado.

## Combo
41. A sequência é a contagem de acertos consecutivos, derivada da lista de respostas. Errar zera a sequência corrente e preserva a maior da batalha.
42. O combo aumenta **dano e moedas** — e tem teto. Sem teto, dois acertos derrubariam qualquer inimigo, e o resto da batalha viraria enfeite.
43. O contador só aparece a partir do segundo acerto seguido: "Combo ×1" não é sequência, e selo permanente em volta do enunciado é ruído.

## Crítico
44. Um acerto **rápido** é crítico e bate mais forte. O limiar é uma régua do banco, não uma constante.
45. **O crítico não é sorteado.** Ele é função do tempo que a resposta levou — número que já era registrado em `question_attempts`. Um dado aleatório daria HP diferente a cada leitura da mesma batalha, e aí seria preciso guardar vida em algum lugar.
46. Resposta sem tempo medido não vira crítico: tempo zero é desconhecido, não instantâneo.

## Moedas
47. Moedas são ganhas por acerto, com bônus por combo. **Errar não tira moeda** — já custou vida.
48. O saldo é **derivado**: moedas iniciais + ganhas − gastas, recalculado a cada leitura. Não há campo de saldo em lugar nenhum.
49. As moedas são **da rodada e morrem com ela**. Não há saldo entre batalhas, loja, nem compra com dinheiro real. Uma moeda persistente viraria economia — e economia dentro de um produto de estudo termina em conteúdo atrás de pagamento (itens 3 e 24 da gamificação).
50. Não há caixa de recompensa, sorteio de item nem raridade (item 34 da gamificação). O preço de cada poder aparece antes do clique.

## Poderes
51. São três, e só três: **Escudo** (impede o dano do próximo erro), **Eliminar** (remove uma alternativa incorreta) e **Dica** (mostra uma pista).
52. Nenhum deles revela a resposta nem destrava conteúdo de estudo. Funcionam nos dois modelos de tela.
53. **A dica é sempre texto já cadastrado** — a primeira frase da explicação da questão ou do comentário da alternativa correta. Gerar um texto para o poder "funcionar" seria inventar conteúdo.
54. **Questão sem explicação não tem dica, e não se cobra por isso**: o pedido é recusado com o motivo e nenhuma moeda sai do saldo.
55. O Eliminar nunca remove a alternativa correta, e a escolha é **estável** (mesmo hash da identidade da questão): sorteio faria a tela mostrar coisas diferentes para a mesma jogada.
56. A alternativa eliminada sai também **da conta do layout**: decidir a arena por um texto que não vai aparecer daria a resposta errada.
57. Cada poder vale uma vez por questão, e só na questão em aberto. Poder sem saldo é recusado dizendo **quantas moedas faltam**.
58. O uso do poder é o **único estado que não dá para derivar** — usar um escudo é uma decisão, não uma consequência. Por isso ele é guardado, junto com o que revelou e o preço pago naquele momento: mudar a tabela de preços não reescreve uma batalha já jogada.

## Escudo e vida
59. O escudo absorve o golpe inteiro do erro seguinte: o dano vai a zero e ninguém apanha.
60. **O escudo protege a vida, não o mérito**: o erro continua zerando o combo e continuando errado nas estatísticas.

## XP
61. O combo da batalha multiplica o XP pela **mesma função já auditada** do modo Combo, com o mesmo teto. Não existe caminho paralelo de XP para o combate.
62. O XP continua passando pelo razão contábil, pelos tetos diários e pelo antiabuso da G1. O combate não cria moeda de XP nova.
63. **"Desafio cumprido" continua medido pela taxa de acerto crua**, não pelo dano. Combo e crítico deixam o monstro cair mais cedo — mas não fazem a plataforma dizer que o candidato foi melhor do que foi.
64. O XP não entra no Mestre Score (item 23 da gamificação). Isso não mudou.

## Som
65. Sete efeitos curtos — `select`, `sword`, `impact`, `monster_attack`, `correct`, `wrong`, `level_up` — **sintetizados na hora**, sem nenhum arquivo de áudio. Sete MP3 seriam sete downloads antes da primeira questão.
66. **Não há música**, e nada toca sozinho: o `AudioContext` só nasce depois de um clique.
67. O som **começa desligado**, com interruptor visível na batalha e escolha gravada por aparelho. A leitura do pedido é que o som deve poder ser desligado; a escolha do padrão é nossa, e vem de onde a plataforma é usada — trabalho, biblioteca, transporte. Fone no ônibus e silêncio no escritório são a mesma pessoa.
68. Navegador sem áudio não quebra a tela: falhar em tocar um efeito nunca interrompe a batalha.

## Configuração
69. Dez réguas novas no banco, no mesmo painel das de layout: tempo do crítico, bônus do crítico, dano por degrau de combo, teto de degraus, moedas por acerto, moedas por degrau, saldo inicial e o preço dos três poderes. Nenhuma delas é constante de código.
70. Régua zerada não derruba a tela: o divisor da estimativa de linhas nunca é zero.

## Qualidade
71. `domain/game/battle.py` continua puro: combo, crítico, dano e moedas são funções sem I/O.
72. 46 testes de domínio, 31 de integração e 36 no cliente. Entre eles, a garantia explícita de que **ler a mesma batalha vinte vezes devolve sempre o mesmo HP e o mesmo saldo**.
73. Migração `battle_power_uses` sobe e desce limpa; `alembic check` sem divergência.
74. A Fase 3 (chefes, campanhas, equipamentos, classes e ranking) **não foi implementada**.

# Critérios de Aceite — Batalha RPG (Fases 1, 2 e 3)

> **Regra que governa esta entrega:** é um RPG 2D por cima de uma plataforma
> séria de concurso. O combate é a **consequência visual** da resposta, nunca a
> fonte dela. Se a animação e a questão disputarem a tela, a questão ganha.

Escopo da **Fase 1**: os dois modelos de tela, a seleção automática entre eles, o
guerreiro, os monstros, as barras de vida, a pergunta, as respostas, acerto,
erro, ataque, dano, explicação e responsividade.

Escopo da **Fase 2**: XP, combo, moedas, poderes, sons e críticos.

Escopo da **Fase 3**: chefes, campanhas, equipamentos, classes e ranking.

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
74. A Fase 3 é a seção seguinte.

---

# Fase 3 — chefes, campanha, equipamento, classe e ranking

> **Regra que governa esta fase, e que nenhuma peça atravessa:**
> **classe e equipamento mudam o combate, nunca a medição.**
>
> Eles alteram vida, dano, moedas e o preço dos poderes. Não escolhem questão,
> não mexem na dificuldade, não destravam conteúdo e não entram no XP. O que
> decide "desafio cumprido", o que limpa um estágio de campanha e o que ordena o
> ranking continua sendo a **taxa de acerto crua** — a mesma com e sem armadura.
> Sem essa linha, um equipamento melhor faria a plataforma dizer que o candidato
> está melhor do que está, que é a única coisa que ela não pode fazer.
>
> O pedido lista os cinco itens da Fase 3 sem detalhá-los. O desenho abaixo é
> nosso, e cada decisão foi tomada contra as proibições que já valiam.

## Classes
75. Quatro classes: **Recruta** (neutra), **Guardião**, **Duelista** e **Estrategista**.
76. **Nenhuma é destravada por nível, liga ou pagamento** (itens 3 e 24 da gamificação). Classe é estilo de jogo, e estilo de jogo se escolhe, não se conquista.
77. A classe de partida é **neutra de propósito**: é contra o combate base que as trocas das outras são declaradas. Um padrão que já desse vantagem esconderia a comparação.
78. **Toda classe ganha de um lado e perde do outro**, e a troca aparece por escrito no arsenal. Uma classe só melhor que as outras não seria escolha.
79. Uma régua ruim não cria um guerreiro que morre antes de jogar: a vida nunca cai abaixo de um golpe do monstro.

## Equipamentos
80. Três espaços — arma, armadura, amuleto — com uma peça inicial em cada. **Ninguém entra na batalha desarmado.**
81. Toda peça acima da inicial é liberada por uma **conquista que já existia na plataforma**, medida em estudo real. Não há sorteio, raridade, caixa de recompensa nem loja (item 34 da gamificação); moedas não compram equipamento.
82. Peça travada **diz qual conquista a libera**. Cadeado sem caminho é armadilha, não objetivo.
83. Equipar algo não conquistado é recusado dizendo o nome da conquista que falta.
84. Peça desconhecida ou no espaço errado **vira a inicial em vez de virar erro**: um slug inválido no banco não pode impedir alguém de estudar.

## Congelamento
85. O loadout é **congelado na rodada**, como as questões já eram. Trocar de armadura no meio da batalha e ter o dano já causado recalculado faria o HP mudar sozinho — e o combate deixaria de ser reconstruível a partir das respostas.
86. Rodada antiga sem loadout gravado usa o combate base, sem quebrar.

## Chefes
87. Um chefe é a batalha contra uma **disciplina fraca real**, escolhida pelo Priority Score que a Inteligência já calculava — a mesma consulta do Boss Battle da G3, não uma segunda régua.
88. **A dificuldade não é inventada**: as questões são as reais daquela disciplina. O que muda é que o chefe aguenta mais golpes, por uma régua do banco.
89. Sem Priority Score não há chefe, e a recusa diz onde calculá-lo.

## Campanha
90. A campanha é a lista das disciplinas mais frágeis do candidato, na **ordem do Priority Score** — a única ordem que ajuda alguém a passar.
91. **Não há mapa de fantasia**: sem Priority Score, a tela diz que não há campanha em vez de desenhar progresso inventado.
92. **Nenhum estágio tranca outro.** Quem quiser começar pelo terceiro começa: matéria de estudo não fica atrás de progresso de jogo (itens 3 e 24).
93. O que pode faltar é questão no banco — e aí o estágio diz **quantas faltam**, em vez de sumir.
94. Um estágio é vencido quando existe uma batalha de chefe encerrada nele com **acerto suficiente**. É o mesmo `achieved` que decide o XP: **equipamento não limpa estágio para ninguém**.
95. A campanha é inteiramente **derivada** — Priority Score mais rodadas encerradas. Não há tabela de progresso a divergir da realidade.

## Ranking
96. Compara **dentro do mesmo contexto** (o cargo do plano ativo) — a mesma consulta da liga, reusada para que as duas telas não divirjam sobre quem disputa com quem (item 21).
97. Quem desligou a comparação **some da tabela e não vê a de ninguém**. É um interruptor só, e ele vale aqui também.
98. **Anonimato por padrão**: só aparece com nome quem escolheu aparecer.
99. Menos de cinco participantes com batalhas suficientes **não vira tabela**, e a tela diz por quê. Abaixo de três batalhas ninguém é ranqueado — duas partidas não dizem quem vai melhor.
100. A ordem é **quantas batalhas foram vencidas pelo acerto**, desempatada por acertos somados. Dano, classe e equipamento não movem ninguém de posição.
101. **Não há percentual de acerto na tabela.** Uma batalha pode terminar antes de as questões acabarem, e dividir por um denominador incerto seria fabricar estatística.
102. A nota da tabela declara, em texto, que nada ali diz coisa alguma sobre aprovação (item 40).

## Qualidade
103. `domain/game/battle.py` e `domain/game/battle_campaign.py` continuam puros, sem I/O.
104. 82 testes de domínio, 45 de integração e 50 no cliente. Entre eles: que o equipamento muda o dano **e não muda o acerto**, que o loadout congelado reproduz sempre a mesma vida, e que poucas batalhas não lideram a tabela.
105. Migração `battle_loadouts` + `battle_run_loadouts` sobe e desce limpa; `alembic check` sem divergência.

---

# Arte cadastrável — monstros, guerreiro e cenário

> **Regra que governa esta entrega:** a silhueta em SVG sempre foi um **padrão,
> não um destino**. Ela garante que a batalha funcione no dia um — sem download,
> sem depender de ninguém desenhar nada. A arte de verdade entra por cima dela, e
> sai se não prestar, sem deploy.
>
> O corolário é que **toda peça é opcional**. Uma tela que só funciona depois de
> alguém subir dez imagens seria uma tela quebrada esperando favor.

## Catálogo
106. Os lugares de arte são **derivados do que a batalha já usa**: as cinco espécies do bestiário, o guerreiro (padrão e por classe) e um cenário por espécie, mais o padrão. Nada aqui inventa uma peça que a tela não desenharia.
107. Chave fora do catálogo é recusada: arte solta ninguém veria, e ocuparia disco para sempre.
108. O painel lista **todos** os lugares, inclusive os vazios, e cada lugar vazio **diz o que a tela desenha no lugar dele**. Uma lista só do que já foi enviado esconderia exatamente o que falta fazer.
109. A cadeia de escolha é curta de propósito — peça da espécie, peça padrão, silhueta. Mais níveis tornariam impossível responder "por que apareceu isto?".

## Envio
110. **O conteúdo do arquivo é o que vale.** Nome e `Content-Type` vêm de quem envia; a validação lê a assinatura real dos bytes (PNG, JPEG, WebP, GIF). Um "monstro.png" que é um executável não entra no disco — e a imagem cadastrada aqui aparece na tela de todo mundo que estuda.
111. O nome do arquivo no disco é **gerado pela aplicação**, nunca o enviado. O nome original é guardado só para quem administra reconhecer a peça.
112. Arquivo vazio e acima do limite são recusados com o motivo. O limite da arte é **separado do limite de PDF** e vive em variável de ambiente: um sprite de 30 MB seria uma tela que não carrega no celular de quem estuda no ônibus.
113. Enviar de novo no mesmo lugar **substitui** a peça anterior, e o arquivo velho sai do disco **depois** do commit — falha no meio deixaria o banco apontando para um arquivo que não existe mais.
114. Só administrador cadastra arte; toda troca e remoção ficam na auditoria.

## Uso na batalha
115. Com arte cadastrada, o monstro é a imagem; sem ela, a silhueta. **Os quatro estados de animação são os mesmos** nos dois casos — a arte não ganha movimento novo nem perde o que havia.
116. O guerreiro sem arte cadastrada continua sendo o personagem que o produto já tinha.
117. O cenário entra como **fundo**, atrás do combate, com um véu escuro por cima para não competir com o enunciado. Sem cenário, o fundo do tema continua.
118. Remover uma peça devolve a silhueta **na questão seguinte**, sem deploy e sem reiniciar a batalha.
119. A imagem é servida por rota **pública**: um `<img>` não carrega o token da aplicação, e desenho de monstro não é dado de ninguém. O cache é longo porque o identificador muda a cada arte enviada.

## Qualidade
120. 10 testes de integração cobrem catálogo, envio, substituição, remoção, recusa de arquivo que não é imagem, recusa de lugar inexistente e a exigência de administrador. 5 no cliente cobrem a troca silhueta ↔ imagem.
121. Migração `battle_assets` sobe e desce limpa; `alembic check` sem divergência.

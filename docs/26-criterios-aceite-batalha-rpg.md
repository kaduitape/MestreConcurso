# Critérios de Aceite — Batalha RPG (Fase 1)

> **Regra que governa esta entrega:** é um RPG 2D por cima de uma plataforma
> séria de concurso. O combate é a **consequência visual** da resposta, nunca a
> fonte dela. Se a animação e a questão disputarem a tela, a questão ganha.

Escopo desta fase: os dois modelos de tela, a seleção automática entre eles, o
guerreiro, os monstros, as barras de vida, a pergunta, as respostas, acerto,
erro, ataque, dano, explicação e responsividade. **Nada de XP extra de combate,
combo, moedas, poderes ou som** — isso é Fase 2, e não foi implementado.

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

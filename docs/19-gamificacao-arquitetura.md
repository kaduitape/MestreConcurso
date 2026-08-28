# 19. Mestre Game Engine — arquitetura, regras e backlog

> **Princípio que governa esta camada:** a gamificação mede **esforço útil e
> desempenho real**, nunca cliques. Um número que sobe sem que o candidato tenha
> ficado melhor é uma mentira com animação — e mentira animada é pior do que
> número nenhum, porque o candidato confia nela e relaxa.
>
> Três regras herdadas do resto da plataforma valem aqui sem exceção:
> **Python calcula, a IA só redige**; **nenhuma estatística sem amostra**; e
> **nada de botão decorativo**.

---

## 1. Arquitetura do Mestre Game Engine

O motor é uma camada **reativa e isolada**. Ele não sabe o que é uma questão ou
um flashcard: recebe **eventos de domínio** já consumados e decide o que isso
vale. Assim, mudar regra de XP não toca em simulado, plano ou revisão.

```
   Serviços existentes (Fases 4–8)
   study_session · practice · simulation · review · error_notebook
              │
              │  emite GameEvent (fato consumado, com métrica real)
              ▼
   ┌──────────────────────────────────────────────────────────┐
   │  app/services/game_engine.py     (orquestração, I/O)      │
   │   1. carrega as regras vigentes (banco, não código)       │
   │   2. chama o domínio para pontuar                         │
   │   3. aplica antiabuso (tetos, janela, validação)          │
   │   4. grava TRANSAÇÃO de XP (nunca só o saldo)             │
   │   5. reavalia nível, streak, missões e conquistas         │
   └──────────────────────────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────────────────────────┐
   │  app/domain/game/           (Python puro, sem I/O)        │
   │   xp.py        · quanto vale cada evento + antiabuso      │
   │   levels.py    · curva de níveis                          │
   │   ranks.py     · fórmula de desempenho real               │
   │   streak.py    · sequência, recorde, proteção             │
   │   missions.py  · geração de missões a partir de sinais    │
   │   achievements.py · avaliação de conquistas               │
   └──────────────────────────────────────────────────────────┘
```

**Por que evento e não chamada direta:** se o `SimulationService` calculasse XP,
a regra de pontuação viveria dentro da regra de simulado. Um dia o produto muda
"simulado vale 300 XP" e alguém precisa mexer no corretor de simulados. Com
evento, o simulado apenas **anuncia o que aconteceu** (`SIMULATION_FINISHED`,
com número de questões, acerto e tempo) e o motor decide o resto.

**Por que as regras moram no banco:** o item 38 pede painel de configuração. Uma
tabela `game_rules` guarda o valor de cada evento, o teto diário e os
multiplicadores; o código traz apenas o **padrão de fábrica**, usado quando não
há linha configurada. Ligar/desligar um recurso é um `UPDATE`, não um deploy.

### Contrato do evento

```python
GameEvent(
    kind: GameEventKind,      # STUDY_SESSION | QUESTIONS_ANSWERED | ...
    user_id: int,
    occurred_at: datetime,
    metrics: dict[str, float],  # minutos, acertos, total, tempo médio…
    reference: str | None,      # public_id da origem — idempotência e auditoria
)
```

`reference` é o que impede pontuar duas vezes o mesmo simulado.

---

## 2. Modelagem do banco

```
game_rules(id, key UNIQUE, label, xp_value, daily_cap, config JSON,
      is_enabled, updated_by_user_id, updated_at)
  A fonte da verdade das regras. O código traz o padrão; esta tabela vence.

gamification_profiles(id, user_id UNIQUE, level, xp_total, xp_into_level,
      rank_slug, rank_score DECIMAL(5,4), rank_components JSON,
      current_streak, longest_streak, last_active_on DATE,
      streak_shields_left, streak_shield_renewed_on DATE,
      missions_completed, achievements_count, computed_at)
  IDX (user_id)
  Saldo desnormalizado para leitura rápida. **A verdade é o razão de XP**: este
  saldo é sempre reconstruível somando `xp_transactions`.

xp_transactions(id, public_id, user_id, event_kind, amount SMALLINT,
      base_amount, multiplier DECIMAL(4,2), reason, reference,
      metrics JSON, capped BOOLEAN, cap_reason, day DATE, created_at)
  IDX (user_id, day), (user_id, created_at), UNIQUE (user_id, event_kind, reference)
  **Audit trail obrigatório (item 37).** Todo ganho vira linha, com o motivo e a
  métrica que o justificou. XP cortado por teto grava a linha com `capped=true` e
  o motivo — o candidato vê por que ganhou menos, em vez de achar que é bug.
  O UNIQUE é o que torna a pontuação idempotente.

levels(level PK, xp_required, title, unlocks JSON)
ranks(slug PK, name, order_index, min_score DECIMAL(5,4), color_token)
  Tabelas de configuração, semeadas e editáveis no painel.

missions(id, public_id, user_id, scope[DAILY|WEEKLY|SPECIAL], title, description,
      kind, target_metric, target_value, current_value, xp_reward,
      priority, difficulty, estimated_minutes, status[PENDING|DONE|EXPIRED|CLAIMED],
      generated_by[RULE|AI], rationale, valid_from DATE, valid_until DATE,
      completed_at, claimed_at, source JSON)
  IDX (user_id, valid_from, status)
  `rationale` guarda **por que esta missão existe** — o sinal real que a gerou.

achievements(id, slug UNIQUE, category, name, description, icon, tier,
      criteria JSON, is_secret, xp_reward, is_active)
user_achievements(id, user_id, achievement_id, unlocked_at, progress JSON)
  UNIQUE (user_id, achievement_id) · IDX (user_id, unlocked_at)

streak_days(id, user_id, day DATE, minutes, tasks_done, qualified BOOLEAN,
      shield_used BOOLEAN)
  UNIQUE (user_id, day)
  Histórico dia a dia: é dele que saem streak atual, recorde e média (item 5).
```

Fases seguintes acrescentam `seasons`, `season_progress`, `leagues`,
`league_members`, `challenges`, `challenge_attempts`, `rewards`, `user_rewards`,
`game_events` — modeladas aqui, criadas quando a fase chegar.

---

## 3. Regras de XP

Valores de fábrica (editáveis no painel):

| Evento | XP | Teto diário | Observação |
|---|---|---|---|
| `STUDY_SESSION` | 100 / 30 min | 400 | proporcional ao **tempo de foco**, não ao relógio aberto |
| `FLASHCARDS_REVIEWED` | 4 / cartão | 200 | cartão só conta uma vez por dia |
| `QUESTIONS_ANSWERED` | 6 / questão | 300 | modulado por dificuldade e acerto |
| `SIMULATION_FINISHED` | 300 | 600 | exige ≥ 10 questões respondidas |
| `ERROR_CLASSIFIED` | 20 / erro | 100 | só causa **confirmada** |
| `DAILY_MISSIONS_DONE` | 250 | 250 | todas as missões do dia |
| `WEEKLY_MISSION_DONE` | 500 | — | missão da semana |

### Antiabuso (item 32) — o que o motor recusa

1. **Teto diário por evento.** Acima dele o XP é zerado e a transação registra `cap_reason`.
2. **Idempotência por referência.** O mesmo simulado, sessão ou missão nunca pontua duas vezes.
3. **Sessão curta não conta.** Foco abaixo de 5 minutos vale zero — abrir e fechar tela não é estudo.
4. **Resposta rápida demais é descartada.** Abaixo de 3 segundos por questão, a questão não entra na contagem: não dá tempo de ler o enunciado.
5. **Questão repetida no mesmo dia não repontua.**
6. **Dificuldade modula.** Questão fácil vale 0,7×; difícil, 1,3×.
7. **Acerto pesa mais que volume.** Um lote com menos de 40% de acerto recebe 0,6× — o objetivo é aprender, não preencher contador.
8. **Tempo ocioso não vira XP.** O motor usa `focus_seconds` da sessão, que já exclui pausa (Fase 4).

O motor **nunca inventa penalidade silenciosa**: toda redução vira transação com motivo legível.

---

## 4. Algoritmo dos ranks

O rank mede **competência**, não acúmulo. XP não entra na fórmula (item 4).

```
rank_score = 0.30 · acerto
           + 0.25 · retenção
           + 0.20 · cobertura do edital
           + 0.15 · desempenho em simulados
           + 0.10 · consistência
```

| Componente | De onde vem (dado real) | Amostra mínima |
|---|---|---|
| acerto | `question_attempts` do candidato | 30 respostas |
| retenção | taxa de recordação em `flashcard_reviews` | 20 revisões |
| cobertura | `user_subject_progress.completion` (Fase 4) | plano ativo |
| simulados | média de `simulation_attempts.analysis.accuracy` | 1 simulado |
| consistência | dias qualificados nos últimos 30 (`streak_days`) | 7 dias |

**Sinal sem amostra vale zero e é declarado** — mesma regra do Priority Score
(Fase 6). O componente aparece na interface como "ainda sem amostra", e o score
mostra a cobertura dos sinais. Um candidato novo é FERRO porque ainda não há o
que medir, não porque é ruim, e a tela diz exatamente isso.

Faixas: FERRO 0 · BRONZE 0,30 · PRATA 0,45 · OURO 0,58 · PLATINA 0,68 ·
DIAMANTE 0,78 · MESTRE 0,86 · GRÃO-MESTRE 0,93.

**O rank pode cair.** Um rank que só sobe não mede nada. A queda é comunicada com
o componente que recuou, nunca como punição.

---

## 5. Sistema de streak

Um dia conta quando o candidato faz **estudo útil**: 20 minutos de foco, **ou**
a missão do dia concluída, **ou** 3 tarefas do plano. Abrir o app não conta.

- `streak_days` grava cada dia com minutos, tarefas e se qualificou;
- **2 proteções por mês**, renovadas no dia 1: um dia perdido consome uma proteção automaticamente e a sequência sobrevive;
- guardamos **atual, recorde, média e histórico** (item 5);
- a interface nunca usa a sequência como ameaça. Quando ela quebra, o texto é factual — "sua sequência de 14 dias terminou; o recorde continua seu" — sem dramatização. Streak que gera ansiedade faz a pessoa estudar por medo de perder um número, o que é o oposto do objetivo.

---

## 6. Sistema de missões

Missão diária nasce de **sinal real** do candidato, com prioridade nesta ordem:

1. **revisão vencida** (Fase 8) — memória prestes a se perder;
2. **erros não classificados** (Fase 6) — erro sem causa não vira aprendizado;
3. **disciplina de maior Priority Score** (Fase 6);
4. **tarefa do plano do dia** (Fase 4);
5. **volume de questões** — só quando nada acima existir.

Cada missão guarda o `rationale` com o número que a gerou: *"Constitucional tem
Priority Score 78, o maior do seu plano"*. Nenhuma missão aparece sem esse porquê.

A missão da semana é uma meta agregada (ex.: 100 questões com 75% de acerto) com
barra de progresso. A **missão especial gerada por IA** (item 7) usa os mesmos
sinais já calculados em Python e pede ao modelo **apenas o texto motivacional** —
o objetivo, a meta e as tarefas continuam sendo conta nossa.

---

## 7. Wireframe — Central de Missões

```
┌────────────────────────────────────────────────────────────────────────┐
│ CENTRAL DE MISSÕES                     🔥 14   LVL 23   OURO II        │
├────────────────────────────────────────────────────────────────────────┤
│ ┌── PROGRESSO DE HOJE ───────────────────────────────────────────────┐ │
│ │  ███████████████░░░░░  72%          XP hoje  780 / 1000            │ │
│ │  3 de 4 missões concluídas                                         │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│ MISSÕES DE HOJE                                                        │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ 🔴 ALTA   Revisar 24 cartões vencidos              ~12 min  +80 XP │ │
│ │ ████████████████░░░░  18/24                                        │ │
│ │ por quê? ▸ 24 cartões venceram; adiar hoje empurra 24 para amanhã  │ │
│ ├────────────────────────────────────────────────────────────────────┤ │
│ │ 🟠 MÉDIA  Classificar 5 erros                      ~8 min  +100 XP │ │
│ │ ██████░░░░░░░░░░░░░░  2/5                                          │ │
│ │ por quê? ▸ 11 erros sem causa registrada                           │ │
│ ├────────────────────────────────────────────────────────────────────┤ │
│ │ ✓ CONCLUÍDA  Estudar Constitucional por 30 min            +120 XP  │ │
│ │ por quê? ▸ Priority Score 78 — o mais alto do seu plano             │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│ ┌── BÔNUS ───────────────────────────────────────────────────────────┐ │
│ │ Concluir todas as missões de hoje                        +250 XP   │ │
│ │ falta 1                                                            │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│ MISSÃO DA SEMANA — OPERAÇÃO PORTUGUÊS                                  │
│ 100 questões · meta 75% de acerto        ████████░░ 62/100 · 78%       │
└────────────────────────────────────────────────────────────────────────┘
```

Estados: **sem plano ativo** → card único convidando a montar o plano, sem
missões inventadas; **tudo concluído** → resumo do dia e a carga de amanhã.

---

## 8. Wireframe — Perfil do candidato

```
┌────────────────────────────────────────────────────────────────────────┐
│  ╭───╮   Carlos Silva                          [Compartilhar semana]   │
│  │ CS│   NÍVEL 23 · 12.480 XP                                          │
│  ╰───╯   ███████████░░░░░░  1.240 / 2.000 para o nível 24              │
├────────────────────────────────────────────────────────────────────────┤
│ ┌── RANK ────────────────────┐ ┌── SEQUÊNCIA ────────────────────────┐ │
│ │  OURO II                   │ │  🔥 14 dias                          │ │
│ │  score 0,61                │ │  recorde 31 · média 9                │ │
│ │  ██████████░░░  → PLATINA  │ │  🛡 2 proteções disponíveis           │ │
│ │  por quê? ▾                │ │  ▪▪▪▪▪▫▪▪▪▪▪▪▪▪ últimos 14 dias      │ │
│ │  acerto      0,71 → 0,213  │ └──────────────────────────────────────┘ │
│ │  retenção    0,82 → 0,205  │ ┌── MESTRE SCORE ─────────────────────┐ │
│ │  cobertura   0,46 → 0,092  │ │  chega na Fase 9 (Analytics).        │ │
│ │  simulados   0,68 → 0,102  │ │  Não será alimentado por XP.         │ │
│ │  consistência ─  sem amostra│ └──────────────────────────────────────┘ │
│ └────────────────────────────┘                                          │
├────────────────────────────────────────────────────────────────────────┤
│  47h estudadas   ·   834 questões   ·   78% acerto   ·   312 cartões    │
├────────────────────────────────────────────────────────────────────────┤
│ CONQUISTAS  12 de 34                                                   │
│ 🔥 Disciplina de Ferro   🎯 Atirador de Elite   🧠 Memória de Aço      │
│ 🔒 ???  (secreta)        🔒 Caçador de Pegadinhas  25 → 8/25           │
└────────────────────────────────────────────────────────────────────────┘
```

O bloco "por quê?" do rank abre as **contribuições que somam o score** — mesma
mecânica do Priority Score. Componente sem amostra aparece como tal.

---

## 9. Wireframe — Você vs Banca *(Fase 2 da gamificação)*

```
┌────────────────────────────────────────────────────────────────────────┐
│ VOCÊ VS CEBRASPE                              baseado em 834 respostas │
│                                                                        │
│        VOCÊ  ███████████████████████░░░░░░░  73                        │
│     CEBRASPE ░░░░░░░░░░░░░░░░░░░░░░███████   27                        │
│                                                                        │
│ POR DISCIPLINA                                                         │
│  Direito Penal      82 × 18   ██████████████████░░░░   (214 respostas) │
│  Português          64 × 36   ████████████░░░░░░░░░░   (198 respostas) │
│  Constitucional     58 × 42   ███████████░░░░░░░░░░░   (142 respostas) │
│  Informática         —        amostra insuficiente     (12 respostas)  │
│                                                                        │
│ EVOLUÇÃO (8 semanas)   ▁▂▃▃▄▅▅▆                                        │
└────────────────────────────────────────────────────────────────────────┘
```

O placar é a taxa de acerto real do candidato naquela banca. Disciplina com
menos de 30 respostas **não recebe placar** — mostra "amostra insuficiente",
como em toda a plataforma.

---

## 10. Wireframe — Jornada da Aprovação *(Fase 2 da gamificação)*

```
┌────────────────────────────────────────────────────────────────────────┐
│ JORNADA DA APROVAÇÃO                          PCDF · Agente · 87 dias  │
│                                                                        │
│  ●───────●───────●───────◉───────○───────○───────○───────🏁            │
│  1º      100     25%     50%     1º      70%     Reta    PROVA         │
│  estudo  quest.  edital  edital  simul.  edital  final                 │
│  ✓       ✓       ✓       agora                                         │
│                                                                        │
│  ETAPA ATUAL — 50% do edital coberto                                   │
│  ████████████░░░░░░░░░░░  46% · faltam 4 pontos                        │
│                                                                        │
│  ⓘ Marcos medem cobertura e desempenho. Não são previsão de aprovação. │
└────────────────────────────────────────────────────────────────────────┘
```

O aviso do rodapé não é decorativo: é o item 40 do pedido, escrito na tela.

---

## 11. Componentes React

**Fase 1:** `XPBar`, `LevelBadge`, `RankBadge`, `StreakCounter`, `MissionCard`,
`MissionProgress`, `AchievementCard`, `AchievementModal`, `DailyProgress`,
`XPToast`, `GameHeader`.
**Fase 2:** `JourneyMap`, `StudyTerritory`, `BattleBar`, `MasterScore`.
**Fase 3:** `LeagueTable`, `SeasonProgress`, `ComboCounter`, `LivesCounter`, `RunClock`
(a rodada de desafio é uma tela só, que muda de regra conforme o modo — um
componente por modo duplicaria a mesma mecânica quatro vezes).

Animação com Framer Motion, já no projeto: *count-up* no XP, *progress ring* na
missão, *glow* discreto ao subir de nível, confete curto só em conquista. Todas
respeitam `prefers-reduced-motion`.

---

## 12. Endpoints FastAPI

**Fase 1**
```
GET   /api/v1/game/profile              perfil, nível, rank com contribuições, streak
GET   /api/v1/game/missions/today       missões do dia + bônus + progresso
POST  /api/v1/game/missions/{id}/claim  resgatar XP de missão concluída
GET   /api/v1/game/achievements         conquistas, com as secretas ocultas
GET   /api/v1/game/xp/history           extrato de XP (o razão, visível ao candidato)
GET   /api/v1/game/streak               atual, recorde, média e histórico
GET   /api/v1/admin/game/rules          regras vigentes
PUT   /api/v1/admin/game/rules/{key}    editar valor, teto e liga/desliga
```

**Fase 2**
```
GET   /api/v1/game/rank/history         evolução diária do rank, com o XP do mesmo período
GET   /api/v1/game/board-battle         placar contra a banca do concurso-alvo
GET   /api/v1/game/journey              marcos da jornada, com o aviso obrigatório
GET   /api/v1/game/territory            mapa do edital, do território mais frágil ao mais firme
```

**Fase 3**
```
GET   /api/v1/game/season                  temporada em curso, com prêmios e critérios
GET   /api/v1/game/season/history          temporadas fechadas, com a posição congelada
GET   /api/v1/game/league                  minha divisão, entre candidatos ao mesmo cargo
GET   /api/v1/game/league/preferences      participo? apareço com nome?
PUT   /api/v1/game/league/preferences      ligar, desligar ou identificar-se
GET   /api/v1/game/challenges/modes        modos, com a regra de vitória de cada um
GET   /api/v1/game/challenges/current      rodada em andamento (no máximo uma)
POST  /api/v1/game/challenges/{mode}       começar uma rodada
GET   /api/v1/game/challenges/runs/{id}    estado da rodada e a questão da vez
POST  /api/v1/game/challenges/runs/{id}/answer   responder
POST  /api/v1/game/challenges/runs/{id}/finish   encerrar (ou abandonar)
GET   /api/v1/game/challenges/history      rodadas anteriores
POST  /api/v1/admin/game/seasons           abrir temporada
POST  /api/v1/admin/game/seasons/{slug}/close    fechar e conceder prêmios
```

**Fases seguintes:** `/game/challenges/friends`, `/game/events`.

---

## 13. Backlog de implementação

| Fase | Escopo | Estado |
|---|---|---|
| **G1** | XP com razão e antiabuso, níveis, streak com proteção, missões diárias por sinal real, conquistas, perfil, Central de Missões, animações, painel de regras | **entregue** |
| **G2** | Histórico de rank na interface, Você vs Banca, Jornada da Aprovação, Mapa do Edital | **entregue** |
| **G3** | Temporadas, ligas por contexto, Boss Battle, Sobrevivência, Combo, Contra o Relógio | **entregue** |
| **G4** | Desafio entre amigos, card compartilhável, eventos especiais e Modo Guerra | a pedido |

O **rank** é calculado e exposto já na G1 (o perfil precisa dele); a G2 acrescenta
o histórico diário, que é o que permite dizer se a preparação subiu ou escorregou.

---

## 14. Critérios de aceite

Fase 1: `docs/20-criterios-aceite-gamificacao-1.md`.
Fase 2: `docs/21-criterios-aceite-gamificacao-2.md`.
Fase 3: `docs/22-criterios-aceite-gamificacao-3.md`.

---

## O que esta camada nunca fará

- Afirmar ou sugerir aprovação. O vocabulário é **progresso, domínio, preparação, desempenho estimado** (item 40).
- Deixar XP influenciar o Mestre Score ou o rank.
- Recompensar tempo ocioso, clique ou tela aberta.
- Usar *loot box* ou recompensa aleatória — toda recompensa tem utilidade declarada (item 34).
- Bloquear conteúdo de estudo atrás de nível, trilha ou liga (itens 3, 24).
- Exibir ranking global indiscriminado; a comparação é entre candidatos do mesmo contexto, e desligável (item 21).

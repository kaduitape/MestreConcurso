import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useReducedMotion } from 'framer-motion'
import { Swords } from 'lucide-react'
import { toast } from 'sonner'
import { GameButton } from '@/components/game/game-button'
import { GameCard } from '@/components/game/game-card'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorState } from '@/components/feedback/error-state'
import { SkeletonList } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import { cn } from '@/lib/utils'
import type { Battle, BattleAnswerResult, BattleMonster, BattlePowerKey } from '@/lib/api/types'
import { selectBattleLayout } from './layout'
import {
  REDUCED_TIMELINE,
  TIMELINE,
  battleReducer,
  initialBattleState,
  type BattleMachineState,
} from './machine'
import { useBattleSound } from './use-sound'
import { useBattleViewport } from './use-viewport'
import { CriticalBadge } from './components/combo-meter'
import { HintPanel, PowerBar } from './components/power-bar'
import { BattleHUD, DamageEffect, SlashEffect } from './components/battle-hud'
import { BattleHeader } from './components/battle-header'
import { ExplanationPanel } from './components/explanation-panel'
import { LongAnswerBattle } from './components/long-answer-battle'
import { Monster, type MonsterMood } from './components/monster'
import { PlayerCharacter, type PlayerMood } from './components/player-character'
import { QuestionPanel } from './components/question-panel'
import { ResultModal } from './components/result-modal'
import { ShortAnswerBattle } from './components/short-answer-battle'

/** O chefe da rodada desenhado com o mesmo componente das alternativas. */
function enemyAsMonster(battle: Battle): BattleMonster {
  return {
    letter: '',
    species: battle.enemy_species,
    name: battle.enemy_name,
    shape: battle.enemy_shape,
    color_token: battle.enemy_color_token,
    accent_token: battle.enemy_accent_token,
    variant: 0,
  }
}

function playerMoodOf(state: BattleMachineState): PlayerMood {
  if (state.outcome === 'defeat') return 'dead'
  if (state.phase === 'PLAYER_ATTACK') return 'attack'
  if (
    state.damageTarget === 'player' &&
    (state.phase === 'DAMAGE' || state.phase === 'RESULT')
  ) {
    return 'hurt'
  }
  return 'idle'
}

function enemyMoodOf(state: BattleMachineState, defeated: boolean): MonsterMood {
  if (defeated) return 'dead'
  if (state.phase === 'ENEMY_ATTACK') return 'attack'
  if (
    state.damageTarget === 'enemy' &&
    (state.phase === 'DAMAGE' || state.phase === 'RESULT')
  ) {
    return 'hurt'
  }
  return 'idle'
}

/**
 * A tela da batalha.
 *
 * Ela orquestra três coisas e nada mais: a máquina de estados (quem ataca,
 * quando o dano aparece), o layout congelado da questão e a troca de questão.
 * O cálculo do combate é do servidor — a tela nunca decide sozinha quanto de
 * vida sobrou, senão o HP da tela e o HP das respostas acabariam divergindo.
 */
export function BattlePage() {
  const queryClient = useQueryClient()
  const viewport = useBattleViewport()
  const reduce = useReducedMotion()
  const timeline = reduce ? REDUCED_TIMELINE : TIMELINE

  const [state, dispatch] = useReducer(battleReducer, initialBattleState)
  const [result, setResult] = useState<BattleAnswerResult | null>(null)
  const [showResultModal, setShowResultModal] = useState(false)
  const sound = useBattleSound()

  const battleQuery = useQuery({
    queryKey: queryKeys.gameBattle(viewport),
    queryFn: () => gameApi.currentBattle(viewport),
    // Atravessar um ponto de corte no meio de uma questão não pode apagar a
    // tela: a batalha anterior fica no lugar até a nova resposta chegar.
    placeholderData: keepPreviousData,
  })
  const battle = battleQuery.data ?? null

  // Cronômetro da questão: o tempo de resposta é do servidor, não do relógio da
  // animação.
  const askedAt = useRef(Date.now())
  const timers = useRef<number[]>([])
  const clearTimers = useCallback(() => {
    timers.current.forEach((id) => window.clearTimeout(id))
    timers.current = []
  }, [])
  const later = useCallback((fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, ms))
  }, [])

  useEffect(() => clearTimers, [clearTimers])

  const question = battle?.run.question ?? null
  const questionId = question?.public_id ?? null

  // A régua do layout roda no cliente porque só ele conhece a largura real.
  // A alternativa eliminada sai da conta do layout: decidir a arena por um
  // texto que não vai aparecer daria a resposta errada.
  const visibleAlternatives = useMemo(
    () =>
      question
        ? question.alternatives.filter(
            (item) => !(battle?.removed_letters ?? []).includes(item.letter),
          )
        : [],
    [question, battle?.removed_letters],
  )

  const decision = useMemo(
    () =>
      battle && question
        ? selectBattleLayout({ alternatives: visibleAlternatives }, viewport, battle.settings)
        : null,
    [battle, question, visibleAlternatives, viewport],
  )
  const decisionRef = useRef(decision)
  decisionRef.current = decision

  // O layout entra quando a questão entra — e fica. Girar o telefone no meio de
  // uma alternativa não pode empurrar o texto para baixo do dedo de quem lê.
  useEffect(() => {
    if (!questionId || !decisionRef.current) return
    clearTimers()
    setResult(null)
    askedAt.current = Date.now()
    dispatch({ type: 'QUESTION_READY', layout: decisionRef.current.layout })
  }, [questionId])

  const invalidateGame = () =>
    queryClient.invalidateQueries({
      predicate: (query) => query.queryKey[0] === 'game' && query.queryKey[1] !== 'battle',
    })

  const start = useMutation({
    mutationFn: () => gameApi.startBattle(viewport),
    onSuccess: (fresh) => {
      setShowResultModal(false)
      setResult(null)
      queryClient.setQueryData(queryKeys.gameBattle(viewport), fresh)
      invalidateGame()
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível abrir a batalha.',
      ),
  })

  const answer = useMutation({
    mutationFn: (letter: string) =>
      gameApi.answerBattle(battle!.run.public_id, viewport, {
        question_public_id: questionId!,
        letter,
        time_seconds: Math.max(1, Math.round((Date.now() - askedAt.current) / 1000)),
      }),
    onSuccess: (payload) => {
      setResult(payload)
      dispatch({
        type: 'RESOLVED',
        isCorrect: payload.is_correct,
        correctLetter: payload.correct_letter,
        damage: payload.damage,
        damageTarget: payload.damage_target,
        isCritical: payload.is_critical,
        shielded: payload.shielded,
        combo: payload.combo,
        coins: payload.coins,
      })
      sound.play(payload.is_correct ? 'sword' : 'monster_attack')
      later(() => {
        dispatch({ type: 'IMPACT' })
        sound.play(payload.shielded ? 'select' : 'impact')
      }, timeline.attack)
      later(() => {
        dispatch({ type: 'SHOW_RESULT' })
        sound.play(payload.is_correct ? 'correct' : 'wrong')
      }, timeline.attack + timeline.damage)
    },
    onError: (error: unknown) => {
      // Devolver o controle é melhor do que deixar a tela presa em "atacando".
      dispatch({ type: 'FAILED' })
      toast.error(error instanceof ApiError ? error.message : 'A resposta não foi registrada.')
    },
  })

  const leave = useMutation({
    mutationFn: () => gameApi.finishRun(battle!.run.public_id, true),
    onSuccess: () => {
      clearTimers()
      queryClient.setQueryData(queryKeys.gameBattle(viewport), null)
      invalidateGame()
    },
  })

  const power = useMutation({
    mutationFn: (chosen: BattlePowerKey) =>
      gameApi.useBattlePower(battle!.run.public_id, viewport, chosen),
    onSuccess: (fresh) => {
      // O poder muda a questão corrente, não a próxima: escrever direto no cache
      // evita um recarregamento que piscaria o enunciado sob a leitura.
      queryClient.setQueryData(queryKeys.gameBattle(viewport), fresh)
      sound.play('level_up')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível usar o poder.'),
  })

  const onSelect = (letter: string) => {
    dispatch({ type: 'SELECT', letter })
    sound.play('select')
    answer.mutate(letter)
  }

  /** Segue para a próxima questão — ou encerra, quando a batalha acabou. */
  const advance = () => {
    if (!result) return
    clearTimers()
    const next = result.battle
    queryClient.setQueryData(queryKeys.gameBattle(viewport), next)
    invalidateGame()

    if (next.status.is_over || next.run.status !== 'RUNNING') {
      dispatch({ type: 'FINISH', outcome: next.status.victory ? 'victory' : 'defeat' })
      setShowResultModal(true)
      return
    }
    dispatch({ type: 'ADVANCE' })
  }

  if (battleQuery.isLoading) return <SkeletonList rows={4} />
  if (battleQuery.isError) {
    return <ErrorState error={battleQuery.error} onRetry={() => battleQuery.refetch()} />
  }

  if (!battle) {
    return (
      <div className="mx-auto max-w-xl">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Swords className="size-5 text-primary" aria-hidden />
              Batalha RPG
            </CardTitle>
            <CardDescription>
              Cada alternativa é um monstro. Você ataca quando acerta; erra e o monstro certo
              contra-ataca. As questões são as mesmas do banco — o combate só muda a
              apresentação.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted">
              A rodada conta como desafio: entra no seu histórico, nas estatísticas e no XP,
              como qualquer outra prática.
            </p>
            <GameButton onClick={() => start.mutate()} loading={start.isPending}>
              Entrar na batalha
            </GameButton>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Enquanto o golpe não chega, a vida mostrada é a de antes: o número muda no
  // impacto, junto com o efeito, e não meio segundo antes dele.
  const showNewStatus =
    result !== null &&
    (state.phase === 'DAMAGE' ||
      state.phase === 'RESULT' ||
      state.phase === 'EXPLANATION' ||
      state.phase === 'VICTORY' ||
      state.phase === 'DEFEAT')
  const status = showNewStatus ? result.battle.status : battle.status
  const enemyDefeated = status.enemy_hp <= 0
  const resolved = state.phase === 'RESULT' || state.phase === 'EXPLANATION'

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <BattleHeader
        battle={battle}
        onLeave={() => leave.mutate()}
        leaving={leave.isPending}
        soundOn={sound.enabled}
        onToggleSound={sound.toggle}
      />

      <PowerBar
        powers={battle.powers}
        coins={status.coins}
        disabled={state.locked || state.phase !== 'QUESTION'}
        pending={power.isPending ? power.variables : null}
        onUse={(chosen) => power.mutate(chosen)}
      />

      {battle.hint && <HintPanel hint={battle.hint} />}

      <GameCard className="space-y-4 p-4 sm:p-5">
        <BattleHUD status={status} enemyName={battle.enemy_name} />

        {/* O palco. Só aqui há movimento; o enunciado e as alternativas ficam
            parados. */}
        <div className="relative flex items-end justify-between gap-4 rounded-xl bg-gradient-to-b from-white/[0.04] to-transparent px-3 pt-2">
          <div className="relative">
            <PlayerCharacter mood={playerMoodOf(state)} />
            <DamageEffect
              amount={state.damage}
              visible={state.damageTarget === 'player' && resolved}
              className="top-2 left-1/2"
            />
          </div>

          {state.layout === 'compact-answer' && (
            <div className="relative">
              <Monster
                monster={enemyAsMonster(battle)}
                mood={enemyMoodOf(state, enemyDefeated)}
              />
              <SlashEffect
                visible={state.phase === 'PLAYER_ATTACK'}
                className="top-2 -left-4"
              />
              <DamageEffect
                amount={state.damage}
                visible={state.damageTarget === 'enemy' && resolved}
                className="top-2 left-1/2"
              />
              <CriticalBadge
                visible={state.isCritical && resolved}
                className="-top-2 left-1/2 -translate-x-1/2"
              />
            </div>
          )}
        </div>
      </GameCard>

      {question && <QuestionPanel question={question} />}

      {question &&
        (state.layout === 'monster-arena' ? (
          <ShortAnswerBattle
            alternatives={visibleAlternatives}
            monsters={battle.monsters}
            state={state}
            onSelect={onSelect}
          />
        ) : (
          <LongAnswerBattle
            alternatives={visibleAlternatives}
            monsters={battle.monsters}
            state={state}
            onSelect={onSelect}
          />
        ))}

      {resolved && result && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3" role="status">
            <p
              className={cn(
                'text-sm font-semibold',
                result.is_correct ? 'text-success' : 'text-danger',
              )}
            >
              {result.is_correct
                ? `Acertou. O ataque tirou ${result.damage} de vida do monstro.`
                : result.shielded
                  ? `Errou — era ${result.correct_letter ?? '—'}. O escudo absorveu o golpe.`
                  : `Errou — era ${result.correct_letter ?? '—'}. O contra-ataque custou ${result.damage} de vida.`}
            </p>
            {result.is_critical && (
              <span className="rounded-full bg-game-gold/15 px-2 py-0.5 text-xs font-black tracking-wide text-game-gold uppercase">
                Crítico · acerto rápido
              </span>
            )}
            {result.combo >= 2 && (
              <span className="rounded-full bg-game-orange/15 px-2 py-0.5 text-xs font-black tracking-wide text-game-orange uppercase">
                Combo ×{result.combo}
              </span>
            )}
            {result.coins > 0 && (
              <span className="font-mono text-xs font-bold tabular-nums text-game-gold">
                +{result.coins} moedas
              </span>
            )}
          </div>

          {state.phase === 'EXPLANATION' && <ExplanationPanel result={result} />}

          <div className="flex flex-wrap gap-2">
            {state.phase === 'RESULT' && (
              <GameButton
                variant="ghost"
                onClick={() => dispatch({ type: 'SHOW_EXPLANATION' })}
              >
                Ver explicação
              </GameButton>
            )}
            <GameButton onClick={advance}>
              {result.battle.status.is_over ? 'Ver resultado' : 'Próxima questão'}
            </GameButton>
          </div>
        </div>
      )}

      <p className="text-xs text-subtle">{decision?.reason}</p>

      <ResultModal
        battle={result?.battle ?? battle}
        open={showResultModal}
        onClose={() => {
          setShowResultModal(false)
          queryClient.setQueryData(queryKeys.gameBattle(viewport), null)
        }}
        onRestart={() => start.mutate()}
        restarting={start.isPending}
      />
    </div>
  )
}

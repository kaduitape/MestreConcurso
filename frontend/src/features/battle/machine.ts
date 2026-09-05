import type { BattleLayout } from '@/lib/api/types'

/**
 * A máquina de estados da batalha.
 *
 * Existe para que as animações não sejam controladas por meia dúzia de booleanos
 * espalhados pelos componentes — cada um deles seria uma chance de a tela ficar
 * travada em "atacando" quando a requisição falha.
 *
 * Ela também é o que garante o item 5: **o layout é congelado quando a questão
 * aparece** e só muda em `NEXT_QUESTION`. Trocar de layout no meio da resposta
 * empurraria o texto sob o dedo de quem está lendo.
 */

export type BattlePhase =
  | 'QUESTION'
  | 'ANSWER_SELECTED'
  | 'PLAYER_ATTACK'
  | 'ENEMY_ATTACK'
  | 'DAMAGE'
  | 'RESULT'
  | 'EXPLANATION'
  | 'NEXT_QUESTION'
  | 'VICTORY'
  | 'DEFEAT'

export interface BattleMachineState {
  phase: BattlePhase
  /** Layout congelado desde a chegada da questão até a próxima. */
  layout: BattleLayout
  selectedLetter: string | null
  correctLetter: string | null
  isCorrect: boolean | null
  damage: number
  /** `null` também quando o escudo absorveu: houve golpe, ninguém apanhou. */
  damageTarget: 'enemy' | 'player' | null
  /** Acerto rápido: bate mais forte e a tela diz por quê. */
  isCritical: boolean
  /** O escudo comprado absorveu este erro. */
  shielded: boolean
  combo: number
  coins: number
  /** Verdadeiro enquanto nenhuma alternativa deve aceitar clique. */
  locked: boolean
  outcome: 'victory' | 'defeat' | null
}

export type BattleEvent =
  | { type: 'QUESTION_READY'; layout: BattleLayout }
  | { type: 'SELECT'; letter: string }
  | {
      type: 'RESOLVED'
      isCorrect: boolean
      correctLetter: string | null
      damage: number
      damageTarget: 'enemy' | 'player' | null
      isCritical: boolean
      shielded: boolean
      combo: number
      coins: number
    }
  | { type: 'IMPACT' }
  | { type: 'SHOW_RESULT' }
  | { type: 'SHOW_EXPLANATION' }
  | { type: 'ADVANCE' }
  | { type: 'FINISH'; outcome: 'victory' | 'defeat' }
  | { type: 'FAILED' }

export const initialBattleState: BattleMachineState = {
  phase: 'QUESTION',
  layout: 'monster-arena',
  selectedLetter: null,
  correctLetter: null,
  isCorrect: null,
  damage: 0,
  damageTarget: null,
  isCritical: false,
  shielded: false,
  combo: 0,
  coins: 0,
  locked: false,
  outcome: null,
}

/**
 * Durações de cada trecho, em milissegundos — a linha do tempo do pedido.
 * Curtas de propósito: a batalha é consequência da resposta, não um filme.
 */
export const TIMELINE = {
  attack: 550,
  damage: 350,
  result: 900,
} as const

/** Com "reduzir animações" ligado, a batalha resolve quase de imediato. */
export const REDUCED_TIMELINE = {
  attack: 120,
  damage: 120,
  result: 400,
} as const

export function battleReducer(
  state: BattleMachineState,
  event: BattleEvent,
): BattleMachineState {
  switch (event.type) {
    case 'QUESTION_READY':
      // O layout entra aqui e não muda mais até a próxima questão.
      return {
        ...initialBattleState,
        layout: event.layout,
        outcome: state.outcome,
        phase: 'QUESTION',
      }

    case 'SELECT':
      if (state.phase !== 'QUESTION' || state.locked) return state
      return {
        ...state,
        phase: 'ANSWER_SELECTED',
        selectedLetter: event.letter,
        locked: true,
      }

    case 'RESOLVED':
      if (state.phase !== 'ANSWER_SELECTED') return state
      return {
        ...state,
        phase: event.isCorrect ? 'PLAYER_ATTACK' : 'ENEMY_ATTACK',
        isCorrect: event.isCorrect,
        correctLetter: event.correctLetter,
        damage: event.damage,
        damageTarget: event.damageTarget,
        isCritical: event.isCritical,
        shielded: event.shielded,
        combo: event.combo,
        coins: event.coins,
      }

    case 'IMPACT':
      if (state.phase !== 'PLAYER_ATTACK' && state.phase !== 'ENEMY_ATTACK') return state
      return { ...state, phase: 'DAMAGE' }

    case 'SHOW_RESULT':
      if (state.phase !== 'DAMAGE') return state
      return { ...state, phase: 'RESULT' }

    case 'SHOW_EXPLANATION':
      if (state.phase !== 'RESULT') return state
      return { ...state, phase: 'EXPLANATION' }

    case 'ADVANCE':
      if (state.phase !== 'RESULT' && state.phase !== 'EXPLANATION') return state
      return { ...state, phase: 'NEXT_QUESTION' }

    case 'FINISH':
      return {
        ...state,
        phase: event.outcome === 'victory' ? 'VICTORY' : 'DEFEAT',
        outcome: event.outcome,
        locked: true,
      }

    case 'FAILED':
      // A resposta não chegou: devolver o controle é melhor do que deixar a
      // tela presa em "atacando" para sempre.
      return { ...state, phase: 'QUESTION', selectedLetter: null, locked: false }

    default:
      return state
  }
}

/** Se a alternativa aceita clique agora. */
export function canSelect(state: BattleMachineState): boolean {
  return state.phase === 'QUESTION' && !state.locked
}

/** O tom visual de cada alternativa depois da resposta. */
export function letterTone(
  state: BattleMachineState,
  letter: string,
): 'idle' | 'selected' | 'correct' | 'wrong' {
  if (state.isCorrect === null) {
    return state.selectedLetter === letter ? 'selected' : 'idle'
  }
  if (state.correctLetter === letter) return 'correct'
  if (state.selectedLetter === letter) return 'wrong'
  return 'idle'
}

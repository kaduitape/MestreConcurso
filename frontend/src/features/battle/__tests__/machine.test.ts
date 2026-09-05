import { describe, expect, it } from 'vitest'
import {
  battleReducer,
  canSelect,
  initialBattleState,
  letterTone,
  type BattleEvent,
  type BattleMachineState,
} from '../machine'

function run(events: BattleEvent[], from: BattleMachineState = initialBattleState) {
  return events.reduce(battleReducer, from)
}

const ready: BattleEvent = { type: 'QUESTION_READY', layout: 'monster-arena' }
const hit: BattleEvent = {
  type: 'RESOLVED',
  isCorrect: true,
  correctLetter: 'B',
  damage: 34,
  damageTarget: 'enemy',
}
const miss: BattleEvent = {
  type: 'RESOLVED',
  isCorrect: false,
  correctLetter: 'C',
  damage: 20,
  damageTarget: 'player',
}

describe('máquina da batalha', () => {
  it('acertar leva ao ataque do jogador; errar, ao do monstro certo', () => {
    expect(run([ready, { type: 'SELECT', letter: 'B' }, hit]).phase).toBe('PLAYER_ATTACK')
    expect(run([ready, { type: 'SELECT', letter: 'A' }, miss]).phase).toBe('ENEMY_ATTACK')
  })

  it('trava as alternativas assim que uma é escolhida', () => {
    const state = run([ready, { type: 'SELECT', letter: 'A' }])
    expect(state.locked).toBe(true)
    expect(canSelect(state)).toBe(false)
    // O segundo clique não troca a resposta já enviada.
    expect(run([{ type: 'SELECT', letter: 'D' }], state).selectedLetter).toBe('A')
  })

  it('ignora eventos fora de ordem em vez de pular etapas', () => {
    expect(run([ready, { type: 'IMPACT' }]).phase).toBe('QUESTION')
    expect(run([ready, { type: 'SHOW_RESULT' }]).phase).toBe('QUESTION')
    expect(run([ready, { type: 'SELECT', letter: 'B' }, { type: 'ADVANCE' }]).phase).toBe(
      'ANSWER_SELECTED',
    )
  })

  it('percorre ataque, dano, resultado e explicação nessa ordem', () => {
    let state = run([ready, { type: 'SELECT', letter: 'B' }, hit])
    state = battleReducer(state, { type: 'IMPACT' })
    expect(state.phase).toBe('DAMAGE')
    state = battleReducer(state, { type: 'SHOW_RESULT' })
    expect(state.phase).toBe('RESULT')
    state = battleReducer(state, { type: 'SHOW_EXPLANATION' })
    expect(state.phase).toBe('EXPLANATION')
    expect(battleReducer(state, { type: 'ADVANCE' }).phase).toBe('NEXT_QUESTION')
  })

  it('o layout só muda quando a questão muda', () => {
    const state = run([
      { type: 'QUESTION_READY', layout: 'compact-answer' },
      { type: 'SELECT', letter: 'A' },
      miss,
      { type: 'IMPACT' },
    ])
    expect(state.layout).toBe('compact-answer')
    expect(
      battleReducer(state, { type: 'QUESTION_READY', layout: 'monster-arena' }).layout,
    ).toBe('monster-arena')
  })

  it('falha de rede devolve o controle em vez de travar a tela', () => {
    const state = run([ready, { type: 'SELECT', letter: 'A' }, { type: 'FAILED' }])
    expect(state.phase).toBe('QUESTION')
    expect(state.selectedLetter).toBeNull()
    expect(canSelect(state)).toBe(true)
  })

  it('o fim da batalha tranca a tela e guarda o desfecho', () => {
    const state = run([ready, { type: 'FINISH', outcome: 'victory' }])
    expect(state.phase).toBe('VICTORY')
    expect(state.outcome).toBe('victory')
    expect(canSelect(state)).toBe(false)
  })

  it('marca a correta e a escolhida depois da resposta', () => {
    const state = run([ready, { type: 'SELECT', letter: 'A' }, miss])
    expect(letterTone(state, 'C')).toBe('correct')
    expect(letterTone(state, 'A')).toBe('wrong')
    expect(letterTone(state, 'D')).toBe('idle')
  })

  it('antes da resposta só destaca a escolha, sem revelar nada', () => {
    const state = run([ready, { type: 'SELECT', letter: 'A' }])
    expect(letterTone(state, 'A')).toBe('selected')
    expect(letterTone(state, 'B')).toBe('idle')
  })
})

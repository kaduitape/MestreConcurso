import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LetterPlate, MonsterHealth } from '../components/monster-hp'
import {
  battleReducer,
  initialBattleState,
  type BattleEvent,
  type BattleMachineState,
} from '../machine'

function run(events: BattleEvent[]): BattleMachineState {
  return events.reduce(battleReducer, initialBattleState)
}

const ready: BattleEvent = { type: 'QUESTION_READY', layout: 'monster-arena' }

function resolved(isCorrect: boolean, damage: number, correctLetter = 'B'): BattleEvent[] {
  return [
    ready,
    { type: 'SELECT', letter: isCorrect ? correctLetter : 'A' },
    {
      type: 'RESOLVED',
      isCorrect,
      correctLetter,
      damage,
      damageTarget: isCorrect ? 'enemy' : 'player',
      isCritical: false,
      shielded: false,
      combo: isCorrect ? 1 : 0,
      coins: isCorrect ? 5 : 0,
    },
    { type: 'IMPACT' },
    { type: 'SHOW_RESULT' },
  ]
}

describe('MonsterHealth', () => {
  it('antes da resposta todo monstro está inteiro', () => {
    render(<MonsterHealth letter="B" state={run([ready])} monsterHp={50} />)
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '50')
    expect(screen.getByText('HP 50')).toBeInTheDocument()
  })

  it('o golpe tira do monstro da alternativa correta', () => {
    render(<MonsterHealth letter="B" state={run(resolved(true, 34))} monsterHp={50} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '16')
  })

  it('golpe forte derruba o monstro de uma vez', () => {
    render(<MonsterHealth letter="B" state={run(resolved(true, 68))} monsterHp={50} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
    expect(screen.getByText('caído')).toBeInTheDocument()
  })

  it('as outras alternativas não apanham', () => {
    render(<MonsterHealth letter="C" state={run(resolved(true, 68))} monsterHp={50} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50')
  })

  it('errar não fere monstro nenhum: quem apanha é o guerreiro', () => {
    render(<MonsterHealth letter="B" state={run(resolved(false, 20))} monsterHp={50} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50')
  })

  it('a barra declara que o escopo é a questão', () => {
    render(<MonsterHealth letter="D" state={run([ready])} monsterHp={50} />)
    expect(
      screen.getByRole('progressbar', {
        name: 'Vida do monstro da alternativa D nesta questão',
      }),
    ).toBeInTheDocument()
  })
})

describe('LetterPlate', () => {
  it('a cor da letra é identidade, não gabarito', () => {
    const { container } = render(<LetterPlate letter="A" tone="idle" />)
    const plate = container.firstElementChild!
    expect(plate).toHaveTextContent('A')
    // Antes da resposta nada de verde nem vermelho de resultado.
    expect(plate.className).not.toContain('bg-success')
  })

  it('depois da resposta a correta fica verde e a escolhida errada vermelha', () => {
    const { container: certa } = render(<LetterPlate letter="C" tone="correct" />)
    expect(certa.firstElementChild!.className).toContain('bg-success')

    const { container: errada } = render(<LetterPlate letter="A" tone="wrong" />)
    expect(errada.firstElementChild!.className).toContain('bg-danger')
  })
})

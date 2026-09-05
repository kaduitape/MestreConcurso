import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Alternative, BattleMonster, BattleStatus } from '@/lib/api/types'
import { BattleHUD } from '../components/battle-hud'
import { LongAnswerBattle } from '../components/long-answer-battle'
import { ShortAnswerBattle } from '../components/short-answer-battle'
import { battleReducer, initialBattleState } from '../machine'

const alternatives: Alternative[] = [
  { public_id: 'a1', letter: 'A', content: 'Sim' },
  { public_id: 'a2', letter: 'B', content: 'Não' },
  {
    public_id: 'a3',
    letter: 'C',
    content: 'Compete privativamente à União legislar sobre direito processual.',
  },
]

const monsters: BattleMonster[] = alternatives.map((item, index) => ({
  letter: item.letter,
  species: 'orc',
  name: `Monstro ${item.letter}`,
  shape: 'brute',
  color_token: 'game-purple',
  accent_token: 'game-blue',
  variant: index,
}))

const answered = [
  { type: 'QUESTION_READY' as const, layout: 'monster-arena' as const },
  { type: 'SELECT' as const, letter: 'A' },
  {
    type: 'RESOLVED' as const,
    isCorrect: false,
    correctLetter: 'C',
    damage: 20,
    damageTarget: 'player' as const,
  },
].reduce(battleReducer, initialBattleState)

describe('ShortAnswerBattle', () => {
  it('toda a região da alternativa é o botão: monstro, letra e texto', async () => {
    const onSelect = vi.fn()
    render(
      <ShortAnswerBattle
        alternatives={alternatives}
        monsters={monsters}
        state={battleReducer(initialBattleState, {
          type: 'QUESTION_READY',
          layout: 'monster-arena',
        })}
        onSelect={onSelect}
      />,
    )

    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(3)
    expect(buttons[0]).toHaveTextContent('Sim')
    // O monstro está dentro do mesmo alvo de toque que o texto.
    expect(buttons[0].querySelector('svg')).not.toBeNull()

    await userEvent.click(buttons[1])
    expect(onSelect).toHaveBeenCalledWith('B')
  })

  it('depois da resposta nenhuma alternativa aceita clique', async () => {
    const onSelect = vi.fn()
    render(
      <ShortAnswerBattle
        alternatives={alternatives}
        monsters={monsters}
        state={answered}
        onSelect={onSelect}
      />,
    )
    for (const button of screen.getAllByRole('button')) {
      expect(button).toBeDisabled()
    }
    await userEvent.click(screen.getAllByRole('button')[2])
    expect(onSelect).not.toHaveBeenCalled()
  })
})

describe('LongAnswerBattle', () => {
  it('mostra o texto inteiro da alternativa, sem cortar', () => {
    render(
      <LongAnswerBattle
        alternatives={alternatives}
        monsters={monsters}
        state={battleReducer(initialBattleState, {
          type: 'QUESTION_READY',
          layout: 'compact-answer',
        })}
        onSelect={vi.fn()}
      />,
    )
    expect(
      screen.getByText('Compete privativamente à União legislar sobre direito processual.'),
    ).toBeInTheDocument()
  })

  it('anuncia a alternativa escolhida para leitores de tela', () => {
    render(
      <LongAnswerBattle
        alternatives={alternatives}
        monsters={monsters}
        state={answered}
        onSelect={vi.fn()}
      />,
    )
    const chosen = screen.getAllByRole('button')[0]
    expect(chosen).toHaveAttribute('aria-pressed', 'true')
  })
})

describe('BattleHUD', () => {
  const status: BattleStatus = {
    player_hp: 80,
    player_max_hp: 100,
    player_hp_ratio: 0.8,
    enemy_hp: 102,
    enemy_max_hp: 204,
    enemy_hp_ratio: 0.5,
    answered: 3,
    correct: 3,
    wrong: 0,
    questions: 8,
    is_over: false,
    victory: false,
    defeat: false,
    outcome_reason: null,
  }

  it('publica as duas vidas com valor, mínimo e máximo', () => {
    render(<BattleHUD status={status} enemyName="Orc" />)

    const player = screen.getByRole('progressbar', { name: 'Vida de Guerreiro' })
    expect(player).toHaveAttribute('aria-valuenow', '80')
    expect(player).toHaveAttribute('aria-valuemax', '100')

    const enemy = screen.getByRole('progressbar', { name: 'Vida de Orc' })
    expect(enemy).toHaveAttribute('aria-valuenow', '102')
    expect(screen.getByText(/Questão 4 de 8/)).toBeInTheDocument()
  })
})

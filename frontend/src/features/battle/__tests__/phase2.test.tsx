import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { BattlePowerOffer } from '@/lib/api/types'
import { ComboMeter, CriticalBadge } from '../components/combo-meter'
import { HintPanel, PowerBar } from '../components/power-bar'
import { playBattleSound, setSoundEnabled, soundEnabled } from '../sound'

const offers: BattlePowerOffer[] = [
  {
    power: 'SHIELD',
    label: 'Escudo',
    description: 'Impede o dano do próximo erro.',
    cost: 25,
    affordable: true,
    used: false,
    removed_letter: null,
    hint: null,
  },
  {
    power: 'ELIMINATE',
    label: 'Eliminar',
    description: 'Remove uma alternativa incorreta.',
    cost: 20,
    affordable: false,
    used: false,
    removed_letter: null,
    hint: null,
  },
  {
    power: 'HINT',
    label: 'Dica',
    description: 'Mostra uma pista tirada da explicação já cadastrada.',
    cost: 15,
    affordable: true,
    used: true,
    removed_letter: null,
    hint: 'A competência é privativa da União.',
  },
]

describe('PowerBar', () => {
  it('mostra o saldo e o preço de cada poder antes do clique', () => {
    render(
      <PowerBar powers={offers} coins={30} disabled={false} pending={null} onUse={vi.fn()} />,
    )
    expect(screen.getByLabelText('30 moedas nesta batalha')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Escudo: .*Custa 25 moedas/ }),
    ).toBeInTheDocument()
  })

  it('poder sem saldo não aceita clique', async () => {
    const onUse = vi.fn()
    render(<PowerBar powers={offers} coins={5} disabled={false} pending={null} onUse={onUse} />)
    const eliminate = screen.getByRole('button', { name: /Eliminar:/ })
    expect(eliminate).toBeDisabled()
    await userEvent.click(eliminate)
    expect(onUse).not.toHaveBeenCalled()
  })

  it('poder já usado aparece como usado e não se compra de novo', () => {
    render(
      <PowerBar powers={offers} coins={99} disabled={false} pending={null} onUse={vi.fn()} />,
    )
    const hint = screen.getByRole('button', { name: 'Dica: já usado nesta questão.' })
    expect(hint).toBeDisabled()
  })

  it('depois de responder, nenhum poder aceita clique', () => {
    render(<PowerBar powers={offers} coins={99} disabled pending={null} onUse={vi.fn()} />)
    for (const button of screen.getAllByRole('button')) {
      expect(button).toBeDisabled()
    }
  })

  it('avisa quem escolheu o poder', async () => {
    const onUse = vi.fn()
    render(
      <PowerBar powers={offers} coins={99} disabled={false} pending={null} onUse={onUse} />,
    )
    await userEvent.click(screen.getByRole('button', { name: /Escudo:/ }))
    expect(onUse).toHaveBeenCalledWith('SHIELD')
  })
})

describe('ComboMeter', () => {
  it('não anuncia sequência antes do segundo acerto seguido', () => {
    const { rerender } = render(<ComboMeter combo={1} />)
    expect(screen.queryByText(/Combo/)).not.toBeInTheDocument()
    rerender(<ComboMeter combo={2} />)
    expect(screen.getByLabelText('Sequência de 2 acertos')).toBeInTheDocument()
  })
})

describe('CriticalBadge', () => {
  it('só aparece durante o golpe', () => {
    const { rerender } = render(<CriticalBadge visible={false} />)
    expect(screen.queryByText('Crítico')).not.toBeInTheDocument()
    rerender(<CriticalBadge visible />)
    expect(screen.getByText('Crítico')).toBeInTheDocument()
  })
})

describe('HintPanel', () => {
  it('mostra a dica marcada como dica', () => {
    render(<HintPanel hint="A competência é privativa da União." />)
    expect(screen.getByRole('note')).toHaveTextContent(
      'Dica: A competência é privativa da União.',
    )
  })
})

describe('som da batalha', () => {
  beforeEach(() => {
    localStorage.clear()
  })
  afterEach(() => {
    localStorage.clear()
  })

  it('começa desligado: nada toca sem alguém pedir', () => {
    expect(soundEnabled()).toBe(false)
  })

  it('a escolha fica gravada neste aparelho', () => {
    setSoundEnabled(true)
    expect(soundEnabled()).toBe(true)
    setSoundEnabled(false)
    expect(soundEnabled()).toBe(false)
  })

  it('desligado, não encosta no áudio do navegador', () => {
    const spy = vi.fn()
    vi.stubGlobal('AudioContext', spy)
    playBattleSound('sword')
    expect(spy).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('sem suporte a áudio, tocar não quebra a tela', () => {
    setSoundEnabled(true)
    vi.stubGlobal(
      'AudioContext',
      class {
        constructor() {
          throw new Error('sem áudio neste navegador')
        }
      },
    )
    expect(() => playBattleSound('impact')).not.toThrow()
    vi.unstubAllGlobals()
  })
})

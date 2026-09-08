import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { BattleHud, BattleStatus } from '@/lib/api/types'
import { BattleBanner, BattleFooter } from '../components/battle-footer'

const status: BattleStatus = {
  player_hp: 80,
  player_max_hp: 100,
  player_hp_ratio: 0.8,
  enemy_hp: 99,
  enemy_max_hp: 204,
  enemy_hp_ratio: 0.48,
  answered: 4,
  correct: 4,
  wrong: 0,
  questions: 10,
  is_over: false,
  victory: false,
  defeat: false,
  outcome_reason: null,
  combo: 4,
  best_combo: 4,
  coins: 47,
  coins_earned: 17,
  coins_spent: 0,
  criticals: 2,
}

const hud: BattleHud = {
  level: 12,
  xp_total: 2450,
  xp_into_level: 320,
  xp_for_next: 500,
  xp_ratio: 0.64,
  focus_minutes: 72,
  focus_target_minutes: 120,
  focus_reason: null,
}

describe('BattleFooter', () => {
  it('mostra nível e o XP que falta para o próximo', () => {
    render(<BattleFooter hud={hud} status={status} />)
    expect(screen.getByText('Nível 12')).toBeInTheDocument()
    expect(screen.getByText('320/500 XP para o próximo nível')).toBeInTheDocument()
  })

  it('no nível máximo não promete um próximo', () => {
    render(<BattleFooter hud={{ ...hud, xp_for_next: null }} status={status} />)
    expect(screen.getByText('2450 XP · nível máximo')).toBeInTheDocument()
  })

  it('o foco aparece contra o alvo que o candidato reservou', () => {
    render(<BattleFooter hud={hud} status={status} />)
    expect(screen.getByText('72/120 min')).toBeInTheDocument()
  })

  it('sem plano de estudo não há barra de foco, e o motivo fica escrito', () => {
    render(
      <BattleFooter
        hud={{
          ...hud,
          focus_minutes: 18,
          focus_target_minutes: null,
          focus_reason: 'Você não reservou minutos para hoje no plano de estudo.',
        }}
        status={status}
      />,
    )
    // O número real continua; o que some é a barra sem denominador.
    expect(screen.getByText('18 min de foco hoje · sem alvo no plano')).toBeInTheDocument()
    expect(screen.queryByText(/min$/)).not.toBeInTheDocument()
  })

  it('alvo zerado também não vira barra', () => {
    render(<BattleFooter hud={{ ...hud, focus_target_minutes: 0 }} status={status} />)
    expect(screen.getByText(/sem alvo no plano/)).toBeInTheDocument()
  })

  it('a vida do guerreiro é a mesma da batalha', () => {
    render(<BattleFooter hud={hud} status={status} />)
    expect(screen.getByText('80/100')).toBeInTheDocument()
  })
})

describe('BattleBanner', () => {
  it('é enfeite: fica fora da árvore de acessibilidade', () => {
    const { container } = render(<BattleBanner words={['Estudo', 'Vitória']} />)
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true')
  })

  it('some nas telas estreitas, para não roubar largura do enunciado', () => {
    const { container } = render(<BattleBanner words={['Estudo']} />)
    const banner = container.firstElementChild!
    expect(banner.className).toContain('hidden')
    expect(banner.className).toContain('xl:flex')
  })
})

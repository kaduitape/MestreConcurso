import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PlanCard } from '../components/plan-card'
import { UsageList } from '../components/usage-list'
import { formatPrice } from '../format'
import type { BillingPlan, Quota } from '@/lib/api/types'

const plan: BillingPlan = {
  slug: 'gratuito',
  name: 'Gratuito',
  description: 'Todo o conteúdo de estudo, com a IA em volume reduzido.',
  price_cents: 0,
  months: 1,
  trial_days: 0,
  is_public: true,
  entitlements: [
    {
      feature: 'ai.tutor',
      label: 'Perguntas ao Mestre IA',
      enabled: true,
      limit: 10,
      period: 'MONTH',
      description: 'Perguntas ao Mestre IA: até 10 por mês.',
    },
    {
      feature: 'simulations',
      label: 'Simulados',
      enabled: true,
      limit: null,
      period: 'MONTH',
      description: 'Simulados: sem limite.',
    },
    {
      feature: 'share_cards',
      label: 'Cards compartilháveis',
      enabled: false,
      limit: null,
      period: 'MONTH',
      description: 'Cards compartilháveis: não incluído neste plano.',
    },
  ],
}

describe('formatPrice', () => {
  it('plano sem preço é grátis, não R$ 0,00', () => {
    expect(formatPrice(0)).toBe('Grátis')
  })

  it('distingue mensal de anual', () => {
    expect(formatPrice(4990)).toContain('/mês')
    expect(formatPrice(47900, 12)).toContain('/ano')
  })
})

describe('PlanCard', () => {
  it('mostra também o que o plano não dá', () => {
    render(<PlanCard plan={plan} />)

    expect(screen.getByText('Perguntas ao Mestre IA: até 10 por mês.')).toBeInTheDocument()
    expect(screen.getByText('Simulados: sem limite.')).toBeInTheDocument()
    expect(
      screen.getByText('Cards compartilháveis: não incluído neste plano.'),
    ).toBeInTheDocument()
  })

  it('marca o plano atual e não oferece assinar de novo', () => {
    render(<PlanCard plan={plan} current onChoose={() => {}} />)

    expect(screen.getByText('plano atual')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /assinar|usar o gratuito/i })).toBeNull()
  })

  it('anuncia o teste quando o plano tem um', () => {
    render(<PlanCard plan={{ ...plan, price_cents: 4990, trial_days: 7 }} />)
    expect(screen.getByText('7 dias de teste')).toBeInTheDocument()
  })
})

const usage: Quota[] = [
  {
    feature: 'ai.tutor',
    label: 'Perguntas ao Mestre IA',
    allowed: true,
    limit: 10,
    used: 4,
    remaining: 6,
    period: 'MONTH',
    resets_on: '2026-04-20',
    reason: '',
  },
  {
    feature: 'simulations',
    label: 'Simulados',
    allowed: true,
    limit: null,
    used: 12,
    remaining: null,
    period: 'MONTH',
    resets_on: null,
    reason: '',
  },
  {
    feature: 'challenges',
    label: 'Rodadas de desafio',
    allowed: false,
    limit: 3,
    used: 3,
    remaining: 0,
    period: 'DAY',
    resets_on: '2026-03-15',
    reason:
      'Você usou 3 de 3 — o limite de “Rodadas de desafio” do seu plano. O contador zera em 16/03/2026. Mudar de plano libera mais agora.',
  },
]

describe('UsageList', () => {
  it('mostra o consumo sobre o limite', () => {
    render(<UsageList items={usage} />)
    expect(screen.getByText('4 / 10')).toBeInTheDocument()
  })

  it('recurso ilimitado não desenha barra nem inventa teto', () => {
    render(<UsageList items={[usage[1]]} />)

    expect(screen.getByText('sem limite')).toBeInTheDocument()
    expect(screen.queryByText('12 / 0')).toBeNull()
  })

  it('limite atingido mostra o motivo e quando renova', () => {
    render(<UsageList items={[usage[2]]} />)

    expect(screen.getByText(/3 de 3/)).toBeInTheDocument()
    expect(screen.getByText(/contador zera em 16\/03\/2026/)).toBeInTheDocument()
  })

  it('a data de renovação aparece para quem ainda tem saldo', () => {
    render(<UsageList items={[usage[0]]} />)
    expect(screen.getByText(/Renova em 20\/04\/2026/)).toBeInTheDocument()
  })
})

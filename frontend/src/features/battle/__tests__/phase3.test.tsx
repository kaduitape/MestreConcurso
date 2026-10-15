import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { BattleArmory, BattleCampaign, BattleRanking } from '@/lib/api/types'
import { ArmoryPanel } from '../components/armory'
import { RankingTable } from '../components/battle-ranking'
import { CampaignMap } from '../components/campaign-map'
import { modifierSummary } from '../modifiers'

const armory: BattleArmory = {
  loadout: {
    class_slug: 'recruta',
    weapon_slug: 'espada-simples',
    armor_slug: 'gibao-de-couro',
    trinket_slug: 'amuleto-de-latao',
    modifiers: {
      damage_percent: 0,
      max_hp_percent: 0,
      coin_percent: 0,
      power_discount_percent: 0,
    },
  },
  classes: [
    {
      slug: 'recruta',
      name: 'Recruta',
      description: 'O combate sem especialização.',
      tradeoff: 'Nenhuma vantagem e nenhuma perda.',
      modifiers: {
        damage_percent: 0,
        max_hp_percent: 0,
        coin_percent: 0,
        power_discount_percent: 0,
      },
    },
    {
      slug: 'duelista',
      name: 'Duelista',
      description: 'Derruba o inimigo mais rápido.',
      tradeoff: '+25% de dano, −20% de vida.',
      modifiers: {
        damage_percent: 25,
        max_hp_percent: -20,
        coin_percent: 0,
        power_discount_percent: 0,
      },
    },
  ],
  equipment: [
    {
      slug: 'espada-simples',
      name: 'Espada simples',
      slot: 'WEAPON',
      description: 'A arma com que todo mundo começa.',
      modifiers: {
        damage_percent: 0,
        max_hp_percent: 0,
        coin_percent: 0,
        power_discount_percent: 0,
      },
      is_unlocked: true,
      requirement_label: null,
    },
    {
      slug: 'lamina-do-acerto',
      name: 'Lâmina do Acerto',
      slot: 'WEAPON',
      description: 'Forjada em mil questões respondidas.',
      modifiers: {
        damage_percent: 10,
        max_hp_percent: 0,
        coin_percent: 0,
        power_discount_percent: 0,
      },
      is_unlocked: false,
      requirement_label: 'Mil Questões',
    },
    {
      slug: 'gibao-de-couro',
      name: 'Gibão de couro',
      slot: 'ARMOR',
      description: 'A proteção inicial.',
      modifiers: {
        damage_percent: 0,
        max_hp_percent: 0,
        coin_percent: 0,
        power_discount_percent: 0,
      },
      is_unlocked: true,
      requirement_label: null,
    },
    {
      slug: 'amuleto-de-latao',
      name: 'Amuleto de latão',
      slot: 'TRINKET',
      description: 'O talismã inicial.',
      modifiers: {
        damage_percent: 0,
        max_hp_percent: 0,
        coin_percent: 0,
        power_discount_percent: 0,
      },
      is_unlocked: true,
      requirement_label: null,
    },
  ],
}

const draft = {
  class_slug: 'recruta',
  weapon_slug: 'espada-simples',
  armor_slug: 'gibao-de-couro',
  trinket_slug: 'amuleto-de-latao',
}

describe('modifierSummary', () => {
  it('declara o que a peça dá e o que ela tira', () => {
    expect(
      modifierSummary({
        damage_percent: 25,
        max_hp_percent: -20,
        coin_percent: 0,
        power_discount_percent: 0,
      }),
    ).toBe('+25% de dano, −20% de vida')
  })

  it('peça neutra diz que é neutra', () => {
    expect(
      modifierSummary({
        damage_percent: 0,
        max_hp_percent: 0,
        coin_percent: 0,
        power_discount_percent: 0,
      }),
    ).toBe('sem alteração no combate')
  })
})

describe('ArmoryPanel', () => {
  it('toda classe mostra a troca por escrito', () => {
    render(
      <ArmoryPanel
        armory={armory}
        draft={draft}
        onDraft={vi.fn()}
        onSave={vi.fn()}
        saving={false}
      />,
    )
    expect(screen.getByText('+25% de dano, −20% de vida.')).toBeInTheDocument()
    expect(screen.getByText('Nenhuma vantagem e nenhuma perda.')).toBeInTheDocument()
  })

  it('peça travada mostra qual conquista a libera', () => {
    render(
      <ArmoryPanel
        armory={armory}
        draft={draft}
        onDraft={vi.fn()}
        onSave={vi.fn()}
        saving={false}
      />,
    )
    const locked = screen.getByRole('button', { name: /travado pela conquista Mil Questões/ })
    expect(locked).toBeDisabled()
    expect(screen.getByText('Conquista: Mil Questões')).toBeInTheDocument()
  })

  it('salvar só fica disponível quando algo muda', async () => {
    const onSave = vi.fn()
    const { rerender } = render(
      <ArmoryPanel
        armory={armory}
        draft={draft}
        onDraft={vi.fn()}
        onSave={onSave}
        saving={false}
      />,
    )
    expect(screen.getByRole('button', { name: 'Salvar equipamento' })).toBeDisabled()

    rerender(
      <ArmoryPanel
        armory={armory}
        draft={{ ...draft, class_slug: 'duelista' }}
        onDraft={vi.fn()}
        onSave={onSave}
        saving={false}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Salvar equipamento' }))
    expect(onSave).toHaveBeenCalled()
  })

  it('deixa claro que equipamento não mexe na medição', () => {
    render(
      <ArmoryPanel
        armory={armory}
        draft={draft}
        onDraft={vi.fn()}
        onSave={vi.fn()}
        saving={false}
      />,
    )
    expect(screen.getByText(/mudam o combate, nunca a medição/)).toBeInTheDocument()
  })
})

describe('CampaignMap', () => {
  const campaign: BattleCampaign = {
    stages: [
      {
        order: 1,
        subject_public_id: 'sub-1',
        label: 'Direito Constitucional',
        priority_score: 0.9,
        battles: 0,
        cleared: false,
        is_locked: false,
        blocked_reason: null,
      },
      {
        order: 2,
        subject_public_id: 'sub-2',
        label: 'Português',
        priority_score: 0.5,
        battles: 2,
        cleared: true,
        is_locked: false,
        blocked_reason: null,
      },
      {
        order: 3,
        subject_public_id: 'sub-3',
        label: 'Informática',
        priority_score: 0.3,
        battles: 0,
        cleared: false,
        is_locked: true,
        blocked_reason: 'O banco tem 4 de 12 questões publicadas nesta disciplina.',
      },
    ],
    cleared: 1,
    total: 3,
    is_complete: false,
    empty_reason: null,
  }

  it('sem Priority Score não desenha mapa nenhum', () => {
    render(
      <CampaignMap
        campaign={{
          stages: [],
          cleared: 0,
          total: 0,
          is_complete: false,
          empty_reason: 'Calcule a prioridade em Inteligência para abrir o mapa.',
        }}
        onFight={vi.fn()}
        pending={null}
      />,
    )
    expect(screen.getByText(/Calcule a prioridade/)).toBeInTheDocument()
  })

  it('nenhum estágio é trancado por outro', async () => {
    const onFight = vi.fn()
    render(<CampaignMap campaign={campaign} onFight={onFight} pending={null} />)

    // O terceiro estágio está disponível mesmo com o primeiro por vencer.
    await userEvent.click(screen.getAllByRole('button')[0])
    expect(onFight).toHaveBeenCalledWith('sub-1')
  })

  it('estágio sem questões no banco diz quantas faltam', () => {
    render(<CampaignMap campaign={campaign} onFight={vi.fn()} pending={null} />)
    expect(screen.getByText(/4 de 12 questões publicadas/)).toBeInTheDocument()
    expect(screen.getAllByRole('button')[2]).toBeDisabled()
  })

  it('conta os estágios vencidos', () => {
    render(<CampaignMap campaign={campaign} onFight={vi.fn()} pending={null} />)
    expect(screen.getByText(/1 de 3 estágios vencidos/)).toBeInTheDocument()
  })
})

describe('RankingTable', () => {
  const ranking: BattleRanking = {
    context_label: 'TRF 3 · Analista Judiciário',
    participants: 6,
    members: [
      {
        position: 1,
        label: 'Candidato #1',
        battles: 9,
        wins: 7,
        correct: 60,
        is_you: false,
        is_named: false,
      },
      {
        position: 2,
        label: 'Você',
        battles: 8,
        wins: 5,
        correct: 48,
        is_you: true,
        is_named: false,
      },
    ],
    your_position: 2,
    empty_reason: null,
    note: 'A ordem é quantas batalhas você venceu pelo acerto. Equipamento e classe mudam o combate, não a posição, e nada aqui diz coisa alguma sobre aprovação.',
  }

  it('grupo pequeno não vira tabela', () => {
    render(
      <RankingTable
        ranking={{
          ...ranking,
          members: [],
          empty_reason: '2 candidato(s) do seu contexto têm ao menos 3 batalhas.',
        }}
      />,
    )
    expect(screen.getByText(/ao menos 3 batalhas/)).toBeInTheDocument()
  })

  it('mostra o contexto e nunca sugere aprovação', () => {
    render(<RankingTable ranking={ranking} />)
    expect(screen.getByText('TRF 3 · Analista Judiciário')).toBeInTheDocument()
    expect(screen.getByText(/nada aqui diz coisa alguma sobre aprovação/)).toBeInTheDocument()
  })

  it('anonimato é o padrão de quem não escolheu aparecer', () => {
    render(<RankingTable ranking={ranking} />)
    expect(screen.getByText('Candidato #1')).toBeInTheDocument()
  })

  it('não publica percentual de acerto', () => {
    render(<RankingTable ranking={ranking} />)
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })
})

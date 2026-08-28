import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LeagueTable } from '../components/league-table'
import { SeasonProgress } from '../components/season-progress'
import type { League, Season } from '@/lib/api/types'

const season: Season = {
  slug: 'temporada-1',
  name: 'Temporada 1',
  description: 'Oito semanas.',
  starts_on: '2026-03-01',
  ends_on: '2026-04-25',
  days_left: 12,
  progress: 0.78,
  standing: {
    seasonal_xp: 3120,
    qualified_days: 22,
    questions: 340,
    challenges: 7,
    position: 4,
    participants: 26,
  },
  rewards: [
    {
      slug: 'selo-temporada',
      label: 'Selo da temporada',
      utility:
        'Marca visual no seu perfil. Não altera o rank, não rende XP e não desbloqueia nenhum conteúdo.',
      criterion: 'Concluir a temporada com pelo menos 5 dias qualificados.',
    },
  ],
  missed_rewards: [
    {
      slug: 'escudo-extra',
      label: 'Escudo de sequência',
      utility: 'Protege um dia perdido da sua sequência no mês seguinte.',
      criterion: 'Terminar a temporada entre os 3 primeiros da sua divisão.',
    },
  ],
  note: 'A temporada mede o esforço do período. Quem mede aprendizado é o rank, e nada da temporada entra nele.',
  empty_reason: null,
}

const league: League = {
  context_label: 'PCDF · Agente de Polícia',
  participants: 26,
  division_index: 0,
  division_label: 'Divisão 1',
  members: [
    {
      position: 1,
      label: 'Marina S.',
      seasonal_xp: 4100,
      active_days: 24,
      is_you: false,
      is_named: true,
    },
    {
      position: 2,
      label: 'Candidato #2',
      seasonal_xp: 3120,
      active_days: 22,
      is_you: true,
      is_named: false,
    },
  ],
  your_position: 2,
  your_division_position: 2,
  note: 'A liga compara o esforço de quem disputa o mesmo cargo no período da temporada. Ela não mede domínio, e sair dela não afeta nada do seu estudo.',
  empty_reason: null,
}

describe('SeasonProgress', () => {
  it('declara que a temporada mede esforço, não domínio', () => {
    render(<SeasonProgress season={season} />)
    expect(screen.getByText(/quem mede aprendizado é o rank/i)).toBeInTheDocument()
  })

  it('todo prêmio mostra utilidade — inclusive o que ainda não veio', () => {
    render(<SeasonProgress season={season} />)

    expect(screen.getByText('Selo da temporada')).toBeInTheDocument()
    expect(screen.getByText(/não desbloqueia nenhum conteúdo/i)).toBeInTheDocument()

    // O prêmio não conquistado aparece com o critério, em vez de sumir.
    expect(screen.getByText('Escudo de sequência')).toBeInTheDocument()
    expect(screen.getByText(/entre os 3 primeiros da sua divisão/i)).toBeInTheDocument()
  })

  it('mostra os números reais do período', () => {
    render(<SeasonProgress season={season} />)
    expect(screen.getByText('3120')).toBeInTheDocument()
    expect(screen.getByText('22')).toBeInTheDocument()
    expect(screen.getByText(/Faltam 12 dias/)).toBeInTheDocument()
  })
})

describe('LeagueTable', () => {
  it('grupo pequeno mostra o motivo em vez de uma tabela', () => {
    render(
      <LeagueTable
        league={{
          ...league,
          members: [],
          empty_reason:
            'São 3 candidato(s) neste contexto. A partir de 5 a tabela passa a dizer alguma coisa.',
        }}
      />,
    )
    expect(screen.getByText(/A partir de 5/)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('identifica o contexto e destaca o próprio candidato', () => {
    render(<LeagueTable league={league} />)

    expect(screen.getByText(/PCDF · Agente de Polícia/)).toBeInTheDocument()
    expect(screen.getByText(/Divisão 1/)).toBeInTheDocument()
    expect(screen.getByText('você')).toBeInTheDocument()
  })

  it('quem não escolheu nome aparece como posição, não como pessoa', () => {
    render(<LeagueTable league={league} />)

    expect(screen.getByText('Marina S.')).toBeInTheDocument()
    expect(screen.getByText('Candidato #2')).toBeInTheDocument()
  })

  it('diz que a comparação é de esforço e é opcional', () => {
    render(<LeagueTable league={league} />)
    expect(screen.getByText(/sair dela não afeta nada do seu estudo/i)).toBeInTheDocument()
  })
})

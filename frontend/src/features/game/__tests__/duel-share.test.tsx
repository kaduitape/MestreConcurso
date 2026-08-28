import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DuelBoard } from '../components/duel-board'
import { ShareCardPreview } from '../components/share-card-preview'
import { WarSchedule } from '../components/war-schedule'
import type { Duel, ShareCard, WarCampaign } from '@/lib/api/types'

const base: Duel = {
  public_id: '01M1',
  code: 'K7QP2XZM',
  status: 'OPEN',
  outcome: 'UNDECIDED',
  headline: 'Aguardando alguém aceitar o desafio.',
  lines: ['Enquanto ninguém aceita, não há placar.'],
  is_challenger: true,
  challenger: {
    display_name: 'Candidato',
    answered: 4,
    correct: 3,
    time_seconds: 90,
    finished: false,
  },
  opponent: null,
  you_won: null,
  my_run: null,
  expires_at: '2026-03-20T12:00:00Z',
  resolved_at: null,
}

describe('DuelBoard', () => {
  it('sem adversário mostra o código do convite, não um placar', () => {
    render(<DuelBoard duel={base} />)

    expect(screen.getByText('K7QP2XZM')).toBeInTheDocument()
    expect(screen.getAllByText(/Aguardando alguém aceitar/).length).toBeGreaterThan(0)
    expect(screen.getByText(/expira em 48 horas/)).toBeInTheDocument()
  })

  it('mostra os dois placares e o motivo do resultado', () => {
    render(
      <DuelBoard
        duel={{
          ...base,
          status: 'FINISHED',
          outcome: 'WIN',
          headline: 'Marina S. venceu por 9 a 4.',
          lines: ['Marina S.: 9 acertos em 240s.', 'Bruno: 4 acertos em 300s.'],
          opponent: {
            display_name: 'Bruno',
            answered: 10,
            correct: 4,
            time_seconds: 300,
            finished: true,
          },
          challenger: {
            display_name: 'Marina S.',
            answered: 10,
            correct: 9,
            time_seconds: 240,
            finished: true,
          },
          you_won: true,
        }}
      />,
    )

    expect(screen.getByText('9')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('Marina S. venceu por 9 a 4.')).toBeInTheDocument()
  })

  it('vitória por ausência aparece com esse nome', () => {
    render(
      <DuelBoard
        duel={{
          ...base,
          status: 'FINISHED',
          outcome: 'WALKOVER',
          headline: 'Marina S. venceu por ausência.',
          lines: [
            'Bruno não concluiu a rodada dentro do prazo.',
            'Vitória por ausência não mede desempenho comparado.',
          ],
          opponent: {
            display_name: 'Bruno',
            answered: 2,
            correct: 2,
            time_seconds: 40,
            finished: false,
          },
        }}
      />,
    )

    expect(screen.getByText(/venceu por ausência/)).toBeInTheDocument()
    expect(screen.getByText(/não mede desempenho comparado/)).toBeInTheDocument()
  })
})

const campaign: WarCampaign = {
  public_id: '01M2',
  status: 'RUNNING',
  starts_on: '2026-03-01',
  days: 3,
  daily_minutes: 120,
  daily_questions: 20,
  days_met: 1,
  days_missed: 1,
  days_left: 1,
  ratio: 0.33,
  is_over: false,
  succeeded: false,
  message: '1 dia cumprido, 1 abaixo da meta. 1 dia restante no período.',
  schedule: [
    { day: '2026-03-01', minutes: 130, questions: 25, met: true, is_future: false },
    { day: '2026-03-02', minutes: 40, questions: 5, met: false, is_future: false },
    { day: '2026-03-03', minutes: 0, questions: 0, met: false, is_future: true },
  ],
  warnings: [
    {
      field: 'daily_minutes',
      message: 'Sua média recente é de 40 minutos por dia, e a meta pede 120.',
    },
  ],
  empty_reason: null,
}

describe('WarSchedule', () => {
  it('mostra a meta, o cumprido e o que ficou abaixo', () => {
    render(<WarSchedule campaign={campaign} />)

    expect(screen.getByText('meta diária: 120 min')).toBeInTheDocument()
    expect(screen.getByText('1 cumpridos')).toBeInTheDocument()
    expect(screen.getByText('1 abaixo da meta')).toBeInTheDocument()
  })

  it('mostra o aviso dado na criação, sem escondê-lo', () => {
    render(<WarSchedule campaign={campaign} />)
    expect(screen.getByText(/média recente é de 40 minutos/)).toBeInTheDocument()
  })

  it('a mensagem do período não acusa o candidato', () => {
    const { container } = render(<WarSchedule campaign={campaign} />)
    const texto = container.textContent!.toLowerCase()

    for (const proibido of ['falhou', 'fracass', 'você não conseguiu']) {
      expect(texto).not.toContain(proibido)
    }
  })
})

const card: ShareCard = {
  display_name: 'Marina',
  headline: 'Marina · Nível 7 · Ouro',
  stats: [
    {
      key: 'questions',
      label: 'Questões',
      value: '340',
      detail: 'Questões respondidas na plataforma.',
    },
  ],
  omitted: ['Taxa de acerto fica de fora: são precisas 30 respostas e há 12.'],
  footer:
    'Números do meu progresso no Concurso Mestre IA. Medem estudo e desempenho, não resultado em prova.',
}

describe('ShareCardPreview', () => {
  it('o rodapé nega previsão de resultado', () => {
    render(<ShareCardPreview card={card} />)
    expect(screen.getByText(/não resultado em prova/)).toBeInTheDocument()
  })

  it('o que ficou de fora aparece com o motivo', () => {
    render(<ShareCardPreview card={card} />)

    expect(screen.getByText('Fora do card')).toBeInTheDocument()
    expect(screen.getByText(/são precisas 30 respostas/)).toBeInTheDocument()
  })

  it('nenhum texto do card promete aprovação', () => {
    const { container } = render(<ShareCardPreview card={card} />)
    const texto = container.textContent!.toLowerCase()

    for (const proibido of ['aprovado', 'vai passar', 'aprovação garantida']) {
      expect(texto).not.toContain(proibido)
    }
  })
})

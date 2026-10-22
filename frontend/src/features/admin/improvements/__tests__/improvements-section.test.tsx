/**
 * A tela do analista tem quatro obrigações acima das outras: **nenhum botão
 * aplica nada**, **"sem amostra" não pode parecer "está tudo certo"**,
 * **`CODE_ONLY` não pode parecer isolamento de banco** e **recusa exige
 * motivo**.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  ImprovementDetector,
  ImprovementFinding,
  ImprovementRun,
} from '@/lib/api/types'

const { improvementsApi } = vi.hoisted(() => ({
  improvementsApi: {
    detectors: vi.fn(),
    setDetector: vi.fn(),
    findings: vi.fn(),
    run: vi.fn(),
    decide: vi.fn(),
  },
}))
vi.mock('@/lib/api/improvements', () => ({ improvementsApi }))

const { ImprovementsSection } = await import('../improvements-section')

function detector(overrides: Partial<ImprovementDetector> = {}): ImprovementDetector {
  return {
    key: 'SUSPECT_ANSWER_KEY',
    label: 'Gabarito suspeito',
    description: 'Questão com acerto muito abaixo do acaso.',
    scope: 'Compara o acerto real com o acerto por acaso. Não lê o enunciado.',
    destination: 'ADMIN',
    is_enabled: true,
    config: { min_attempts: 30, chance_divisor: 2, mute_days: 90 },
    defaults: { min_attempts: 30, chance_divisor: 2, mute_days: 90 },
    last_run_at: '2026-10-22T10:00:00Z',
    last_status: 'FOUND',
    last_detail: '1 de 4 questão(ões) com amostra suficiente',
    last_found: 1,
    ...overrides,
  }
}

function finding(overrides: Partial<ImprovementFinding> = {}): ImprovementFinding {
  return {
    public_id: 'F1',
    detector: 'SUSPECT_ANSWER_KEY',
    detector_label: 'Gabarito suspeito',
    status: 'OPEN',
    severity: 'HIGH',
    destination: 'ADMIN',
    title: 'Gabarito suspeito: o homicídio qualificado',
    detail: '8% de acerto em 100 respostas, contra 25% esperados por acaso.',
    proposal: 'Conferir o gabarito desta questão na tela de questões.',
    evidence: { attempts: 100, correct: 8 },
    target_kind: 'QUESTION',
    target_public_id: 'Q1',
    measured_waste_cents: null,
    first_seen_at: '2026-10-22T10:00:00Z',
    last_seen_at: '2026-10-22T10:00:00Z',
    seen_count: 1,
    decided_at: null,
    decision_reason: null,
    muted_until: null,
    resolved_at: null,
    reopened_count: 0,
    ...overrides,
  }
}

function run(overrides: Partial<ImprovementRun> = {}): ImprovementRun {
  return {
    isolation: 'CODE_ONLY',
    detectors: [
      {
        key: 'SUSPECT_ANSWER_KEY',
        label: 'Gabarito suspeito',
        status: 'FOUND',
        detail: '1 de 4 questão(ões) com amostra suficiente',
        found: 1,
      },
    ],
    opened: 1,
    updated: 0,
    resolved: 0,
    reopened: 0,
    muted: 0,
    ...overrides,
  }
}

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ImprovementsSection />
    </QueryClientProvider>,
  )
}

describe('ImprovementsSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    improvementsApi.detectors.mockResolvedValue([detector()])
    improvementsApi.findings.mockResolvedValue([finding()])
    improvementsApi.run.mockResolvedValue(run())
    improvementsApi.decide.mockResolvedValue(finding({ status: 'ACCEPTED' }))
  })

  it('diz que o analista não aplica nada, não usa IA e não lê o repositório', async () => {
    renderSection()

    expect(
      await screen.findByText('O analista propõe. Quem decide e corrige é você.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/não chamam IA nenhuma/)).toBeInTheDocument()
    expect(screen.getByText(/não lê o repositório/)).toBeInTheDocument()
  })

  it('não oferece nenhum botão que aplique a mudança', async () => {
    renderSection()
    await screen.findByText(/Gabarito suspeito: o homicídio/)

    const botoes = screen.getAllByRole('button').map((item) => item.textContent ?? '')
    expect(botoes.some((texto) => /aplicar/i.test(texto))).toBe(false)
    expect(
      screen.getByText(/A correção é feita na tela correspondente/),
    ).toBeInTheDocument()
  })

  it('mostra o achado com a evidência e a proposta em texto', async () => {
    renderSection()

    expect(await screen.findByText(/8% de acerto em 100 respostas/)).toBeInTheDocument()
    expect(screen.getByText(/Conferir o gabarito desta questão/)).toBeInTheDocument()
    expect(screen.getByText('alta')).toBeInTheDocument()
  })

  it('sem custo medido, nenhuma economia é afirmada', async () => {
    renderSection()
    await screen.findByText(/8% de acerto/)

    expect(screen.queryByText(/Gasto medido no problema/)).not.toBeInTheDocument()
  })

  it('com custo medido, o valor aparece', async () => {
    improvementsApi.findings.mockResolvedValue([
      finding({ measured_waste_cents: '250' }),
    ])
    renderSection()

    expect(await screen.findByText(/Gasto medido no problema/)).toBeInTheDocument()
    expect(screen.getByText(/R\$\s?2,50/)).toBeInTheDocument()
  })

  it('recusar exige motivo antes de habilitar o registro', async () => {
    renderSection()
    await screen.findByText(/8% de acerto/)

    await userEvent.click(screen.getByRole('button', { name: /Recusar/ }))
    const registrar = screen.getByRole('button', { name: 'Registrar recusa' })
    expect(registrar).toBeDisabled()

    await userEvent.type(screen.getByLabelText('Motivo da recusa'), 'É difícil de propósito')
    expect(registrar).toBeEnabled()
  })

  it('"sem amostra" aparece como aviso próprio, nunca como limpo', async () => {
    improvementsApi.run.mockResolvedValue(
      run({
        opened: 0,
        detectors: [
          {
            key: 'ROUTE_INERT',
            label: 'Regra de roteamento inerte',
            status: 'NOT_ENOUGH_DATA',
            detail: 'nenhuma regra foi avaliada em 50 decisões',
            found: 0,
          },
        ],
      }),
    )
    renderSection()

    await userEvent.click(screen.getByRole('button', { name: /Rodar agora/ }))

    expect(
      await screen.findByText('Detector sem amostra não fecha nada'),
    ).toBeInTheDocument()
    expect(screen.getByText(/ausência de medição não é ausência de problema/)).toBeInTheDocument()
    expect(screen.getByText(/sem amostra para rodar:/)).toBeInTheDocument()
  })

  it('isolamento só por código não pode parecer isolamento de banco', async () => {
    renderSection()

    await userEvent.click(screen.getByRole('button', { name: /Rodar agora/ }))

    expect(
      await screen.findByText('sem credencial restrita — garantia só do código'),
    ).toBeInTheDocument()
  })

  it('com credencial restrita, a tela diz que ela está em uso', async () => {
    improvementsApi.run.mockResolvedValue(run({ isolation: 'DB_READONLY' }))
    renderSection()

    await userEvent.click(screen.getByRole('button', { name: /Rodar agora/ }))

    expect(
      await screen.findByText('credencial restrita de banco em uso'),
    ).toBeInTheDocument()
  })

  it('o detector declara o alcance e os limiares editáveis', async () => {
    renderSection()

    expect(await screen.findByText(/Alcance: Compara o acerto real/)).toBeInTheDocument()
    expect(screen.getByLabelText('min_attempts do detector Gabarito suspeito')).toHaveValue(30)
  })

  it('um achado fechado pelo detector não oferece decisão', async () => {
    improvementsApi.findings.mockResolvedValue([
      finding({ status: 'RESOLVED', resolved_at: '2026-10-22T11:00:00Z' }),
    ])
    renderSection()

    expect(await screen.findByText('fechado pelo detector')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Vou fazer/ })).not.toBeInTheDocument()
  })
})

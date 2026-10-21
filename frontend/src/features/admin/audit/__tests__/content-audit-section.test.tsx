/**
 * A tela do portão tem uma obrigação acima das outras: **o que não foi
 * conferido não pode parecer aprovado**. É isso que estes testes cobram.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AuditRule, ContentAudit } from '@/lib/api/types'

const { contentAuditApi } = vi.hoisted(() => ({
  contentAuditApi: {
    rules: vi.fn(),
    saveRule: vi.fn(),
    audits: vi.fn(),
    run: vi.fn(),
  },
}))
vi.mock('@/lib/api/content-audit', () => ({ contentAuditApi }))

const { ContentAuditSection } = await import('../content-audit-section')

const regras: AuditRule[] = [
  {
    key: 'question.alternative_repeated',
    label: 'Alternativa repetida',
    description: 'Duas alternativas com o mesmo texto.',
    applies_to: ['QUESTION'],
    default_severity: 'BLOCKER',
    severity: 'BLOCKER',
    is_enabled: true,
    config: {},
  },
  {
    key: 'question.near_duplicate',
    label: 'Questão quase igual a outra',
    description: 'Enunciado muito parecido com o de outra questão.',
    applies_to: ['QUESTION'],
    default_severity: 'WARNING',
    severity: 'WARNING',
    is_enabled: false,
    config: { min_score: 0.85 },
  },
]

const laudo: ContentAudit = {
  public_id: 'laudo1',
  target_kind: 'QUESTION',
  target_public_id: 'q-123',
  verdict: 'BLOCKED',
  trigger: 'PUBLISH',
  blocked_publication: true,
  findings: [
    {
      rule: 'question.alternative_repeated',
      severity: 'BLOCKER',
      message: 'Duas alternativas têm o mesmo texto.',
      evidence: {},
    },
    {
      rule: 'content.topic_outside_notice',
      severity: 'NOT_CHECKED',
      message: 'Não há edital analisado para comparar, então o tópico não foi conferido.',
      evidence: {},
    },
  ],
  summary: { blockers: 1, warnings: 0, not_checked: 1, compared_questions: 42 },
  created_at: '2026-10-21T10:00:00Z',
}

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ContentAuditSection />
    </QueryClientProvider>,
  )
}

describe('ContentAuditSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    contentAuditApi.rules.mockResolvedValue(regras)
    contentAuditApi.audits.mockResolvedValue({
      items: [laudo],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    })
    contentAuditApi.saveRule.mockResolvedValue({ ...regras[0], severity: 'WARNING' })
  })

  it('mostra o que não foi conferido como item próprio, não como aprovação', async () => {
    renderSection()

    expect(await screen.findByText(/não foi conferido/)).toBeInTheDocument()
    expect(screen.getByText('Não conferido:')).toBeInTheDocument()
    expect(screen.getByText(/1 item\(ns\) não puderam ser conferidos/)).toBeInTheDocument()
  })

  it('declara o alcance da conferência', async () => {
    renderSection()

    expect(
      await screen.findByText(/Comparado com 42 questões da disciplina/),
    ).toBeInTheDocument()
  })

  it('a publicação barrada aparece com essas palavras', async () => {
    renderSection()

    expect(await screen.findByText('publicação barrada')).toBeInTheDocument()
    expect(screen.getByText('Bloqueado')).toBeInTheDocument()
  })

  it('regra desligada fica à vista, no aviso e na própria linha', async () => {
    renderSection()

    expect(await screen.findByText('Há regra desligada')).toBeInTheDocument()
    expect(screen.getByText('desligada')).toBeInTheDocument()
  })

  it('o seletor mostra a severidade que vale hoje, não o padrão do código', async () => {
    renderSection()
    await screen.findByText('Questão quase igual a outra')

    const seletores = screen.getAllByRole('combobox') as HTMLSelectElement[]
    expect(seletores[0].value).toBe('BLOCKER')
    expect(seletores[1].value).toBe('WARNING')
  })

  it('mudar a severidade salva a regra', async () => {
    renderSection()
    await screen.findByText('Alternativa repetida')

    const seletor = screen.getAllByRole('combobox')[0]
    await userEvent.selectOptions(seletor, 'WARNING')

    await waitFor(() =>
      expect(contentAuditApi.saveRule).toHaveBeenCalledWith('question.alternative_repeated', {
        is_enabled: true,
        severity: 'WARNING',
      }),
    )
  })
})

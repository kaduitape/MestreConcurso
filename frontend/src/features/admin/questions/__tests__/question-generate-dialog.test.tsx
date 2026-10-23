/**
 * A tela de geração de questões tem duas obrigações acima das outras:
 *
 * 1. **Não prometer o que a conferência não faz.** "Gabarito conferido" é forma
 *    e citação; se a leitura do material está correta, só uma pessoa julga — e a
 *    tela precisa dizer isso antes de alguém clicar.
 * 2. **Mostrar o descarte.** O que não passou aparece com o motivo, porque é o
 *    que diz se o problema está no material ou no modelo.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { QuestionAdmin, QuestionGeneration } from '@/lib/api/types'

const { adminQuestionsApi } = vi.hoisted(() => ({
  adminQuestionsApi: { generate: vi.fn(), markReviewed: vi.fn() },
}))
vi.mock('@/lib/api/questions', () => ({ adminQuestionsApi }))

const { QuestionGenerateDialog } = await import('../question-generate-dialog')

function questao(): QuestionAdmin {
  return {
    public_id: 'Q1',
    statement: 'Assinale a alternativa que define o fenômeno da crase.',
    kind: 'MULTIPLE_CHOICE',
    difficulty: 'MEDIUM',
    origin: 'AI_GENERATED',
    status: 'DRAFT',
    year: null,
    subject_name: 'Português',
    explanation: 'A definição está no material.',
    source_note: null,
    tags: [],
    alternatives: [],
    ai_suggestion: { quote: 'A crase é a contração da preposição A' },
    stats: null,
    reviewed_at: null,
    created_at: '2026-10-23T10:00:00Z',
  } as unknown as QuestionAdmin
}

function geracao(overrides: Partial<QuestionGeneration> = {}): QuestionGeneration {
  return {
    created: [questao()],
    discarded: [
      {
        statement: '(CESPE/2023) Assinale a alternativa correta sobre a crase.',
        reason: 'o enunciado se apresenta como questão de banca',
      },
    ],
    reasons: { FABRICATED_PROVENANCE: 1 },
    duplicated: 0,
    skipped_reason: null,
    model: 'gpt-4o-mini',
    prompt_version: 'v1',
    ...overrides,
  }
}

function renderDialog() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <QuestionGenerateDialog
        open
        onOpenChange={() => {}}
        subjects={[]}
        topics={[]}
        onSubjectChange={() => {}}
        onGenerated={() => {}}
      />
    </QueryClientProvider>,
  )
}

describe('QuestionGenerateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    adminQuestionsApi.generate.mockResolvedValue(geracao())
  })

  it('avisa que a conferência de origem não garante que o gabarito está certo', () => {
    renderDialog()

    expect(
      screen.getByText(/não diz que o gabarito está certo/),
    ).toBeInTheDocument()
    expect(screen.getByText(/só uma pessoa julga/)).toBeInTheDocument()
  })

  it('não gera com material curto', async () => {
    renderDialog()

    const botao = screen.getByRole('button', { name: /Gerar questões/ })
    expect(botao).toBeDisabled()

    await userEvent.type(screen.getByLabelText(/Material/), 'x'.repeat(200))
    expect(botao).toBeEnabled()
  })

  it('mostra o que entrou como rascunho e o que foi descartado, com o motivo', async () => {
    renderDialog()

    await userEvent.type(screen.getByLabelText(/Material/), 'x'.repeat(210))
    await userEvent.click(screen.getByRole('button', { name: /Gerar questões/ }))

    expect(await screen.findByText(/1 em rascunho · 1 descartada/)).toBeInTheDocument()
    expect(screen.getByText('gerada por IA')).toBeInTheDocument()
    expect(screen.getByText('rascunho')).toBeInTheDocument()
    expect(screen.getByText(/se apresenta como questão de banca/)).toBeInTheDocument()
    expect(screen.getByText(/enunciado se apresentando como questão de banca: 1/)).toBeInTheDocument()
  })
})

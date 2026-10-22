/**
 * A tela da árvore tem três obrigações acima das outras: **não sugerir
 * pré-requisito** onde o edital não declara, **não transformar amostra pequena
 * em porcentagem** e **não misturar lacuna da plataforma com desempenho do
 * candidato**.
 */
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  KnowledgeEvidence,
  KnowledgeSubject,
  KnowledgeTopic,
  KnowledgeTree,
} from '@/lib/api/types'

const { gameApi } = vi.hoisted(() => ({ gameApi: { knowledgeTree: vi.fn() } }))
vi.mock('@/lib/api/game', () => ({ gameApi }))

const { KnowledgeTreePage } = await import('../knowledge-tree-page')

function evidence(overrides: Partial<KnowledgeEvidence> = {}): KnowledgeEvidence {
  return {
    answers: 0,
    correct: 0,
    questions_available: 0,
    lessons_available: 0,
    lessons_done: 0,
    mind_maps_available: 0,
    cards: 0,
    reviews: 0,
    recalled: 0,
    days_since_activity: null,
    answers_missing: 12,
    ...overrides,
  }
}

function topic(overrides: Partial<KnowledgeTopic> = {}): KnowledgeTopic {
  return {
    label: 'Crase',
    state: 'MASTERED',
    reason: '90% de acerto em 20 respostas',
    topic_id: 10,
    descendants: 0,
    page_number: 8,
    accuracy: 0.9,
    evidence: evidence({ answers: 20, correct: 18, questions_available: 40, answers_missing: 0 }),
    ...overrides,
  }
}

function subject(overrides: Partial<KnowledgeSubject> = {}): KnowledgeSubject {
  return {
    label: 'Língua Portuguesa',
    state: 'MASTERED',
    reason: '90% de acerto em 20 respostas',
    subject_id: 1,
    color_token: 'subject-portugues',
    weight: '2.00',
    questions_count: 20,
    evidence_level: 'OFFICIAL',
    accuracy: 0.9,
    evidence: evidence({ answers: 20, correct: 18, answers_missing: 0 }),
    topics: [topic()],
    ...overrides,
  }
}

function tree(overrides: Partial<KnowledgeTree> = {}): KnowledgeTree {
  return {
    competition_public_id: 'c1',
    competition_name: 'Concurso da Árvore',
    notice_title: 'Edital nº 1/2026',
    subjects: [subject()],
    summary: {
      subjects: 1,
      topics: 1,
      measured: 1,
      mastered: 1,
      needs_review: 0,
      in_progress: 0,
      not_started: 0,
      not_linked: 0,
      no_material: 0,
      measurable: 1,
    },
    attention: [],
    unavailable_reason: null,
    ...overrides,
  }
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <KnowledgeTreePage />
    </QueryClientProvider>,
  )
}

describe('KnowledgeTreePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    gameApi.knowledgeTree.mockResolvedValue(tree())
  })

  it('diz que a árvore não é ordem de pré-requisito e que nada tranca conteúdo', async () => {
    renderPage()

    expect(
      await screen.findByText(/A árvore é a hierarquia do edital, não uma ordem de estudo/),
    ).toBeInTheDocument()
    expect(screen.getByText(/não declara pré-requisito/)).toBeInTheDocument()
    expect(screen.getByText(/Nenhum estado aqui tranca conteúdo/)).toBeInTheDocument()
  })

  it('sem concurso principal, explica o que falta em vez de desenhar vazio', async () => {
    gameApi.knowledgeTree.mockResolvedValue(
      tree({
        subjects: [],
        notice_title: null,
        unavailable_reason: 'Escolha seu concurso principal para a árvore nascer do edital dele.',
      }),
    )
    renderPage()

    expect(await screen.findByText('Ainda não há árvore para desenhar')).toBeInTheDocument()
    expect(screen.getByText(/Escolha seu concurso principal/)).toBeInTheDocument()
  })

  it('mostra o rótulo do edital, o peso e a procedência da disciplina', async () => {
    renderPage()

    expect(await screen.findByText('Língua Portuguesa')).toBeInTheDocument()
    expect(screen.getByText('oficial')).toBeInTheDocument()
    expect(screen.getByText(/Peso 2.00 no edital/)).toBeInTheDocument()
  })

  it('amostra pequena aparece como respostas que faltam, nunca como porcentagem', async () => {
    gameApi.knowledgeTree.mockResolvedValue(
      tree({
        subjects: [
          subject({
            accuracy: null,
            state: 'IN_PROGRESS',
            reason: '3 resposta(s) registrada(s); faltam 9 para a taxa de acerto deixar de oscilar',
            topics: [
              topic({
                state: 'IN_PROGRESS',
                accuracy: null,
                reason:
                  '3 resposta(s) registrada(s); faltam 9 para a taxa de acerto deixar de oscilar',
                evidence: evidence({ answers: 3, correct: 3, answers_missing: 9 }),
              }),
            ],
          }),
        ],
      }),
    )
    renderPage()

    expect(await screen.findAllByText(/faltam 9 para a taxa de acerto/)).not.toHaveLength(0)
    expect(screen.queryByText(/100% de acerto/)).not.toBeInTheDocument()
  })

  it('separa a lacuna da plataforma do desempenho do candidato', async () => {
    gameApi.knowledgeTree.mockResolvedValue(
      tree({
        subjects: [
          subject({
            topics: [
              topic(),
              topic({
                label: 'Colocação pronominal',
                state: 'NOT_LINKED',
                reason: 'este tópico do edital ainda não foi vinculado ao catálogo',
                topic_id: null,
                accuracy: null,
                evidence: evidence(),
              }),
            ],
          }),
        ],
        summary: {
          subjects: 1,
          topics: 2,
          measured: 1,
          mastered: 1,
          needs_review: 0,
          in_progress: 0,
          not_started: 0,
          not_linked: 1,
          no_material: 0,
          measurable: 1,
        },
      }),
    )
    renderPage()

    expect(await screen.findByText(/1 tópico que a plataforma ainda/)).toBeInTheDocument()
    expect(screen.getByText(/Isto é lacuna nossa, não sua/)).toBeInTheDocument()
    expect(screen.getByText(/1 tópico sem vínculo com o catálogo/)).toBeInTheDocument()
    // A disciplina continua com a taxa medida sobre o que foi medido.
    expect(screen.getAllByText('90% de acerto').length).toBeGreaterThan(0)
  })

  it('a fila do que estudar diz que lacuna da plataforma não entra nela', async () => {
    gameApi.knowledgeTree.mockResolvedValue(tree({ attention: ['Crase', 'Vírgula'] }))
    renderPage()

    expect(await screen.findByText('Por onde começar hoje')).toBeInTheDocument()
    expect(screen.getByText(/a providência dele é nossa/)).toBeInTheDocument()
  })

  it('o ramo declara quantos subtópicos entraram na conta dele', async () => {
    gameApi.knowledgeTree.mockResolvedValue(
      tree({ subjects: [subject({ topics: [topic({ descendants: 3 })] })] }),
    )
    renderPage()

    expect(await screen.findByText('+ 3 subtópicos')).toBeInTheDocument()
  })
})

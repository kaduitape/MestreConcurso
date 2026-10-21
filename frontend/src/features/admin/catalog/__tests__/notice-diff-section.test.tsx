/**
 * A tela da retificação tem duas obrigações acima das outras: **órfão não pode
 * parecer apagado** e **deduzido não pode parecer conferido**.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { NoticeDiff } from '@/lib/api/types'

const { noticeDiffApi } = vi.hoisted(() => ({
  noticeDiffApi: { list: vi.fn(), compare: vi.fn(), markReviewed: vi.fn() },
}))
const { adminCatalogApi } = vi.hoisted(() => ({ adminCatalogApi: { competitions: vi.fn() } }))
vi.mock('@/lib/api/notice-diff', () => ({ noticeDiffApi }))
vi.mock('@/lib/api/catalog', () => ({ adminCatalogApi }))

const { NoticeDiffSection } = await import('../notice-diff-section')

function diff(overrides: Partial<NoticeDiff> = {}): NoticeDiff {
  return {
    public_id: 'd1',
    competition_public_id: 'c1',
    from_notice_title: 'Edital nº 1/2026',
    to_notice_title: 'Retificação nº 1',
    changes: [
      {
        scope: 'EVENT',
        kind: 'CHANGED',
        label: 'Prova objetiva',
        before: '10/05/2026',
        after: '21/06/2026',
        detail: 'A data mudou.',
        topic_id: null,
        subject_id: null,
        evidence_level: 'OFFICIAL',
      },
      {
        scope: 'TOPIC',
        kind: 'REMOVED',
        label: 'Regência',
        before: 'Português',
        after: null,
        detail: 'Tópico que saiu do conteúdo programático.',
        topic_id: 11,
        subject_id: null,
        evidence_level: null,
      },
    ],
    impacts: [
      {
        action: 'ORPHANED',
        topic_label: 'Regência',
        topic_id: 11,
        reason:
          'O edital não cobra mais este tópico. O conteúdo continua no ar — quem decide o destino dele é uma pessoa.',
        content: {
          kind: 'TRAINING_LESSON',
          public_id: 'aula-reg',
          title: 'Regência sem mistério',
        },
      },
    ],
    summary: { added: 0, removed: 1, changed: 1, orphaned: 1, missing: 0, inferred: 0 },
    reviewed_at: null,
    created_at: '2026-10-21T12:00:00Z',
    ...overrides,
  }
}

function renderSection(diffs: NoticeDiff[]) {
  noticeDiffApi.list.mockResolvedValue({
    items: diffs,
    total: diffs.length,
    page: 1,
    page_size: 10,
    pages: 1,
  })
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <NoticeDiffSection />
    </QueryClientProvider>,
  )
}

describe('NoticeDiffSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    adminCatalogApi.competitions.mockResolvedValue({
      items: [{ public_id: 'c1', name: 'TRT 5ª Região', year: 2026 }],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    })
  })

  it('diz que comparar não muda nada e que órfão não é apagado', async () => {
    renderSection([diff()])

    expect(await screen.findByText('Comparar não muda nada')).toBeInTheDocument()
    expect(screen.getAllByText(/órfão, nunca apagado/).length).toBeGreaterThan(0)
  })

  it('a data que mudou mostra os dois lados', async () => {
    renderSection([diff()])

    expect(await screen.findByText('10/05/2026')).toBeInTheDocument()
    expect(screen.getByText(/21\/06\/2026/)).toBeInTheDocument()
  })

  it('dado conferido e dado deduzido recebem marcas diferentes', async () => {
    renderSection([
      diff({
        changes: [
          {
            scope: 'EVENT',
            kind: 'CHANGED',
            label: 'Prova objetiva',
            before: '10/05/2026',
            after: '21/06/2026',
            detail: 'A data mudou.',
            topic_id: null,
            subject_id: null,
            evidence_level: 'INFERRED',
          },
        ],
        summary: { added: 0, removed: 0, changed: 1, orphaned: 0, missing: 0, inferred: 1 },
      }),
    ])

    expect(await screen.findByText('deduzido pela IA')).toBeInTheDocument()
    expect(
      screen.getByText(/Parte do que mudou foi deduzido, não conferido/),
    ).toBeInTheDocument()
  })

  it('o conteúdo órfão aparece pelo nome, com o motivo, e sem botão de apagar', async () => {
    renderSection([diff()])

    expect(await screen.findByText('Regência sem mistério')).toBeInTheDocument()
    expect(
      screen.getAllByText(/quem decide o destino dele é uma pessoa/).length,
    ).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /apagar|excluir|remover/i })).toBeNull()
  })

  it('tópico novo sem conteúdo aparece como falta', async () => {
    renderSection([
      diff({
        impacts: [
          {
            action: 'MISSING',
            topic_label: 'Concordância',
            topic_id: 12,
            reason: 'Tópico novo sem conteúdo. Entra no próximo plano de geração.',
            content: null,
          },
        ],
        summary: { added: 1, removed: 0, changed: 0, orphaned: 0, missing: 1, inferred: 0 },
      }),
    ])

    expect(await screen.findByText('Tópicos novos sem conteúdo')).toBeInTheDocument()
    expect(screen.getByText('Concordância')).toBeInTheDocument()
  })

  it('marcar como lida chama a api e some depois', async () => {
    noticeDiffApi.markReviewed.mockResolvedValue(diff({ reviewed_at: '2026-10-21T13:00:00Z' }))
    renderSection([diff()])

    await userEvent.click(await screen.findByRole('button', { name: /Marcar como lida/ }))

    await waitFor(() => expect(noticeDiffApi.markReviewed).toHaveBeenCalledWith('d1'))
  })

  it('comparação já lida não oferece o botão', async () => {
    renderSection([diff({ reviewed_at: '2026-10-21T13:00:00Z' })])

    expect(await screen.findByText('lida')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Marcar como lida/ })).toBeNull()
  })
})

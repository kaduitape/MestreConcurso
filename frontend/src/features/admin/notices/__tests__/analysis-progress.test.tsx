import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import { AnalysisProgressPanel } from '../analysis-progress'
import type { AnalysisState } from '@/lib/api/types'

const state: AnalysisState = {
  notice_public_id: 'ABC',
  status: 'AWAITING_CONFIRMATION',
  started_at: '2026-08-23T12:00:00Z',
  finished_at: '2026-08-23T12:01:00Z',
  error: null,
  coverage: { total: 15, official: 12, inferred: 2, not_found: 1, proven_ratio: 0.8 },
  steps: [
    { key: 'read', label: 'Lendo o arquivo enviado', status: 'DONE', detail: '84 KB lidos', at: null },
    { key: 'extract', label: 'Extraindo o texto do PDF', status: 'DONE', detail: '84 páginas', at: null },
    {
      key: 'index',
      label: 'Indexando para busca semântica',
      status: 'SKIPPED',
      detail: 'sem modelo de embeddings configurado',
      at: null,
    },
    { key: 'ai', label: 'Identificando os dados do edital', status: 'DONE', detail: '1600 tokens', at: null },
  ],
}

function renderPanel(data: AnalysisState) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(data), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AnalysisProgressPanel publicId="ABC" />
    </QueryClientProvider>,
  )
}

describe('AnalysisProgressPanel', () => {
  it('mostra cada etapa com o que foi feito, não um spinner genérico', async () => {
    renderPanel(state)

    expect(await screen.findByText('Extraindo o texto do PDF')).toBeInTheDocument()
    expect(screen.getByText('84 páginas')).toBeInTheDocument()
    // Etapa pulada explica o motivo em vez de sumir da tela.
    expect(screen.getByText('sem modelo de embeddings configurado')).toBeInTheDocument()
  })

  it('resume a cobertura da extração com números reais', async () => {
    renderPanel(state)
    await waitFor(() =>
      expect(screen.getByText(/campo\(s\) com citação conferida/)).toBeInTheDocument(),
    )
  })

  it('exibe o erro quando a análise falha', async () => {
    renderPanel({
      ...state,
      status: 'FAILED',
      error: 'O PDF parece digitalizado e o OCR não está disponível neste ambiente.',
      steps: [{ ...state.steps[0]!, status: 'FAILED', detail: null }],
    })

    expect(await screen.findByText('A análise não foi concluída')).toBeInTheDocument()
    expect(screen.getByText(/OCR não está disponível/)).toBeInTheDocument()
  })
})

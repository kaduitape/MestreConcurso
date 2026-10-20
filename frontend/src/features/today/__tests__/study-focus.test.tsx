import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { StudyFocus } from '@/lib/api/types'
import { queryKeys } from '@/lib/query-client'
import { StudyFocusCard } from '../study-focus-card'

/**
 * A regra que estes testes vigiam: **sem dado real não há número**. Sem
 * concurso escolhido não há contagem; sem data de prova também não — e nos
 * dois casos a tela escreve o motivo em vez de mostrar um traço mudo.
 */

function renderWith(focus: StudyFocus) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity, refetchOnMount: false } },
  })
  client.setQueryData(queryKeys.studyFocus, focus)
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <StudyFocusCard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const VAZIO: StudyFocus = {
  competition_public_id: null,
  competition_name: null,
  organization_name: null,
  exam_date: null,
  days_remaining: null,
  unavailable_reason: 'Nenhum concurso principal escolhido.',
}

describe('cartão do concurso principal', () => {
  it('sem escolha, convida a escolher e diz o motivo', () => {
    renderWith(VAZIO)

    expect(screen.getByText('Escolha seu concurso')).toBeInTheDocument()
    expect(screen.getByText('Nenhum concurso principal escolhido.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver concursos' })).toBeInTheDocument()
  })

  it('com data de prova, mostra a contagem', () => {
    renderWith({
      ...VAZIO,
      competition_public_id: 'c1',
      competition_name: 'Tribunal Regional Federal',
      organization_name: 'TRF 1ª Região',
      exam_date: '2026-12-01',
      days_remaining: 42,
      unavailable_reason: null,
    })

    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('dias para a prova')).toBeInTheDocument()
    expect(screen.getByText('Tribunal Regional Federal')).toBeInTheDocument()
  })

  it('um dia no singular', () => {
    renderWith({
      ...VAZIO,
      competition_public_id: 'c1',
      competition_name: 'Concurso',
      days_remaining: 1,
      exam_date: '2026-12-01',
      unavailable_reason: null,
    })

    expect(screen.getByText('dia para a prova')).toBeInTheDocument()
  })

  it('sem data no edital, escreve o motivo no lugar do número', () => {
    renderWith({
      ...VAZIO,
      competition_public_id: 'c1',
      competition_name: 'Concurso sem data',
      days_remaining: null,
      unavailable_reason: 'O edital ainda não trouxe a data da prova.',
    })

    expect(screen.getByText('O edital ainda não trouxe a data da prova.')).toBeInTheDocument()
    // E nenhum número aparece fingindo ser prazo.
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('a data da prova não escorrega de dia por causa do fuso', () => {
    renderWith({
      ...VAZIO,
      competition_public_id: 'c1',
      competition_name: 'Concurso',
      exam_date: '2026-03-01',
      days_remaining: 10,
      unavailable_reason: null,
    })

    // Interpretar "2026-03-01" como UTC exibiria 28 de fevereiro no Brasil.
    expect(screen.getByText(/1 de março de 2026/)).toBeInTheDocument()
  })
})

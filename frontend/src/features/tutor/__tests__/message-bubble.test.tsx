import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MessageBubble } from '../message-bubble'
import type { ChatMessage } from '@/lib/api/types'

const base: ChatMessage = {
  public_id: 'M1',
  role: 'ASSISTANT',
  content: '',
  claims: [],
  sources: [],
  computed_context: {},
  is_refusal: false,
  refusal_reason: null,
  grounding_ratio: null,
  model_slug: 'gpt-4o-mini',
  input_tokens: 900,
  output_tokens: 200,
  created_at: '2026-08-24T12:00:00Z',
}

const mixed: ChatMessage = {
  ...base,
  grounding_ratio: 0.5,
  claims: [
    {
      text: 'A prova será em 15 de março de 2026.',
      kind: 'FACT',
      status: 'CITED',
      quote: 'A prova objetiva será aplicada no dia 15 de março de 2026',
      chunk_id: 12,
      page_number: 2,
      document_title: 'Edital PCDF',
      note: null,
    },
    {
      text: 'O recurso tem prazo de 30 dias.',
      kind: 'FACT',
      status: 'UNSOURCED',
      quote: 'prazo de trinta dias',
      chunk_id: null,
      page_number: null,
      document_title: null,
      note: 'a citação não foi localizada no material recuperado',
    },
    {
      text: 'Comece pelos blocos com mais questões.',
      kind: 'GUIDANCE',
      status: 'COMPUTED',
      quote: null,
      chunk_id: null,
      page_number: null,
      document_title: null,
      note: null,
    },
  ],
  sources: [
    {
      chunk_id: 12,
      document_title: 'Edital PCDF',
      page_number: 2,
      score: 0.83,
      excerpt: 'A prova objetiva será aplicada no dia 15 de março de 2026…',
    },
  ],
}

describe('MessageBubble', () => {
  it('mostra a origem da afirmação conferida no próprio texto', () => {
    render(<MessageBubble message={mixed} />)

    expect(screen.getByText('A prova será em 15 de março de 2026.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Edital PCDF, p\. 2/ })).toBeInTheDocument()
  })

  it('marca visivelmente a afirmação sem origem em vez de escondê-la', async () => {
    render(<MessageBubble message={mixed} />)

    const chip = screen.getByRole('button', { name: /sem origem/ })
    expect(chip).toBeInTheDocument()
    expect(screen.getByText('O recurso tem prazo de 30 dias.')).toBeInTheDocument()

    await userEvent.click(chip)
    expect(
      screen.getByText('a citação não foi localizada no material recuperado'),
    ).toBeInTheDocument()
  })

  it('orientação de estudo não recebe selo de origem', () => {
    render(<MessageBubble message={mixed} />)

    expect(screen.getByText('Comece pelos blocos com mais questões.')).toBeInTheDocument()
    // Dois chips apenas: um por afirmação factual.
    expect(screen.getAllByRole('button', { name: /Edital PCDF|sem origem/ })).toHaveLength(2)
  })

  it('resume quanto da resposta tem origem conferida', () => {
    render(<MessageBubble message={mixed} />)
    expect(screen.getByText(/50% das afirmações com origem conferida/)).toBeInTheDocument()
  })

  it('abre os trechos consultados sob demanda', async () => {
    render(<MessageBubble message={mixed} />)

    await userEvent.click(screen.getByRole('button', { name: /1 trecho\(s\) consultado/ }))
    expect(screen.getByText(/proximidade 83%/)).toBeInTheDocument()
  })

  it('recusa aparece como recusa, com o motivo', () => {
    render(
      <MessageBubble
        message={{
          ...base,
          is_refusal: true,
          refusal_reason: 'Não localizei isso na sua base indexada.',
        }}
      />,
    )

    expect(screen.getByText('Não vou responder isso')).toBeInTheDocument()
    expect(screen.getByText('Não localizei isso na sua base indexada.')).toBeInTheDocument()
  })

  it('mensagem do candidato é exibida sem selos', () => {
    render(<MessageBubble message={{ ...base, role: 'USER', content: 'Qual a data?' }} />)

    expect(screen.getByText('Qual a data?')).toBeInTheDocument()
    expect(screen.queryByText(/origem conferida/)).not.toBeInTheDocument()
  })
})

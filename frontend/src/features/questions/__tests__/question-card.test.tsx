import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { QuestionCard } from '../question-card'
import type { AnswerFeedback, Question } from '@/lib/api/types'

const question: Question = {
  public_id: 'Q1',
  statement: 'A prescrição da pretensão punitiva é',
  kind: 'MULTIPLE_CHOICE',
  difficulty: 'HARD',
  origin: 'OFFICIAL',
  year: 2024,
  subject_name: 'Direito Penal',
  tags: [],
  alternatives: [
    { public_id: 'A1', letter: 'A', content: 'Causa de aumento de pena' },
    { public_id: 'A2', letter: 'B', content: 'Causa de extinção da punibilidade' },
  ],
  stats: { attempts: 4, accuracy: null, average_time_seconds: 90 },
}

const feedback: AnswerFeedback = {
  is_correct: false,
  is_blank: false,
  selected_letter: 'A',
  correct_letter: 'B',
  correct_feedback: 'A prescrição extingue a punibilidade.',
  selected_feedback: 'Aumento de pena é outra coisa.',
  explanation: 'Ver art. 107 do Código Penal.',
  time_seconds: 12,
}

describe('QuestionCard', () => {
  it('não exibe taxa de acerto quando a amostra é pequena', () => {
    render(<QuestionCard question={question} />)
    expect(screen.getByText(/amostra insuficiente/i)).toBeInTheDocument()
  })

  it('mostra o comentário da marcada e o da correta após responder', async () => {
    const onAnswer = vi.fn().mockResolvedValue(feedback)
    render(<QuestionCard question={question} onAnswer={onAnswer} />)

    await userEvent.click(screen.getByText('Causa de aumento de pena'))
    await userEvent.click(screen.getByRole('button', { name: /responder/i }))

    expect(onAnswer).toHaveBeenCalledWith('A', expect.any(Number))
    expect(await screen.findByText(/Você marcou/)).toBeInTheDocument()
    expect(screen.getByText(/Aumento de pena é outra coisa/)).toBeInTheDocument()
    expect(screen.getByText(/A prescrição extingue a punibilidade/)).toBeInTheDocument()
    expect(screen.getByText(/art\. 107/)).toBeInTheDocument()
  })

  it('permite deixar em branco e informa a resposta certa', async () => {
    const onAnswer = vi
      .fn()
      .mockResolvedValue({ ...feedback, is_blank: true, selected_letter: null })
    render(<QuestionCard question={question} onAnswer={onAnswer} />)

    await userEvent.click(screen.getByRole('button', { name: /deixar em branco/i }))

    expect(onAnswer).toHaveBeenCalledWith(null, expect.any(Number))
    expect(await screen.findByText(/Em branco/)).toBeInTheDocument()
  })

  it('sem manipulador de resposta, a questão é apenas leitura', () => {
    render(<QuestionCard question={question} />)
    expect(screen.queryByRole('button', { name: /responder/i })).not.toBeInTheDocument()
  })
})

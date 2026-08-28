import { useEffect, useState } from 'react'
import { CheckCircle2, CircleAlert, Loader2, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { AnswerFeedback, Question } from '@/lib/api/types'
import { DIFFICULTY_LABEL, DIFFICULTY_TONE, formatPercent } from './helpers'

interface QuestionCardProps {
  question: Question
  index?: number
  /** Resolve a questão e devolve a correção; ausente em modo somente leitura. */
  onAnswer?: (letter: string | null, timeSeconds: number) => Promise<AnswerFeedback>
}

export function QuestionCard({ question, index, onAnswer }: QuestionCardProps) {
  const [selected, setSelected] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<AnswerFeedback | null>(null)
  const [sending, setSending] = useState(false)
  const [startedAt, setStartedAt] = useState(() => Date.now())

  useEffect(() => {
    setSelected(null)
    setFeedback(null)
    setStartedAt(Date.now())
  }, [question.public_id])

  const answered = feedback !== null

  async function submit() {
    if (!onAnswer || answered) return
    setSending(true)
    try {
      const seconds = Math.min(3600, Math.round((Date.now() - startedAt) / 1000))
      setFeedback(await onAnswer(selected, seconds))
    } finally {
      setSending(false)
    }
  }

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div className="flex flex-wrap items-center gap-2">
          {index !== undefined && <Badge variant="outline">Questão {index + 1}</Badge>}
          {question.subject_name && <Badge variant="primary">{question.subject_name}</Badge>}
          <Badge variant={DIFFICULTY_TONE[question.difficulty]}>
            {DIFFICULTY_LABEL[question.difficulty]}
          </Badge>
          {question.year && <Badge variant="outline">{question.year}</Badge>}
          {question.origin === 'AI_GENERATED' && <Badge variant="info">Gerada por IA</Badge>}
          {question.stats && (
            <span className="text-xs text-subtle">
              {question.stats.accuracy === null
                ? `${question.stats.attempts} resposta(s) — amostra insuficiente para taxa de acerto`
                : `${formatPercent(question.stats.accuracy, 0)} de acerto em ${question.stats.attempts} respostas`}
            </span>
          )}
        </div>

        <p className="text-sm leading-relaxed whitespace-pre-line">{question.statement}</p>

        <ul className="space-y-2">
          {question.alternatives.map((alternative) => {
            const isSelected = selected === alternative.letter
            const isCorrect = answered && feedback?.correct_letter === alternative.letter
            const isWrongPick = answered && isSelected && !feedback?.is_correct
            return (
              <li key={alternative.public_id}>
                <button
                  type="button"
                  disabled={answered || !onAnswer}
                  onClick={() => setSelected(isSelected ? null : alternative.letter)}
                  className={cn(
                    'flex w-full items-start gap-3 rounded-md border p-3 text-left text-sm transition',
                    'disabled:cursor-default',
                    isCorrect && 'border-success bg-success-soft/50',
                    isWrongPick && 'border-danger bg-danger-soft/50',
                    !answered && isSelected && 'border-primary bg-primary-soft/40',
                    !answered && !isSelected && 'border-border hover:bg-surface-muted',
                    answered && !isCorrect && !isWrongPick && 'border-border opacity-70',
                  )}
                >
                  <span className="mt-0.5 font-semibold">{alternative.letter}</span>
                  <span className="flex-1">{alternative.content}</span>
                  {isCorrect && <CheckCircle2 className="size-4 shrink-0 text-success" />}
                  {isWrongPick && <XCircle className="size-4 shrink-0 text-danger" />}
                </button>
              </li>
            )
          })}
        </ul>

        {onAnswer && !answered && (
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={submit} disabled={sending || selected === null}>
              {sending && <Loader2 className="size-4 animate-spin" />} Responder
            </Button>
            <Button variant="ghost" onClick={submit} disabled={sending}>
              Deixar em branco
            </Button>
          </div>
        )}

        {feedback && (
          <div className="space-y-3 rounded-md border border-border bg-surface-muted p-4 text-sm">
            <p className="flex items-center gap-2 font-medium">
              {feedback.is_blank ? (
                <>
                  <CircleAlert className="size-4 text-warning" /> Em branco. A resposta certa é
                  a {feedback.correct_letter}.
                </>
              ) : feedback.is_correct ? (
                <>
                  <CheckCircle2 className="size-4 text-success" /> Você acertou.
                </>
              ) : (
                <>
                  <XCircle className="size-4 text-danger" /> Você marcou{' '}
                  {feedback.selected_letter}; a certa é a {feedback.correct_letter}.
                </>
              )}
            </p>
            {feedback.selected_feedback && !feedback.is_correct && (
              <p className="text-muted">
                <span className="font-medium text-foreground">
                  Por que a {feedback.selected_letter} está errada:{' '}
                </span>
                {feedback.selected_feedback}
              </p>
            )}
            {feedback.correct_feedback && (
              <p className="text-muted">
                <span className="font-medium text-foreground">
                  Por que a {feedback.correct_letter} está certa:{' '}
                </span>
                {feedback.correct_feedback}
              </p>
            )}
            {feedback.explanation && <p className="text-muted">{feedback.explanation}</p>}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

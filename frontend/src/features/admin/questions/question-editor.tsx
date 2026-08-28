import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { ApiError } from '@/lib/api/client'
import { adminQuestionsApi } from '@/lib/api/questions'
import type { AlternativeInput } from '@/lib/api/questions'
import type { QuestionDifficulty, Subject } from '@/lib/api/types'
import { DIFFICULTY_LABEL } from '@/features/questions/helpers'

const LETTERS = ['A', 'B', 'C', 'D', 'E']

function emptyAlternatives(): AlternativeInput[] {
  return LETTERS.slice(0, 4).map((letter) => ({
    letter,
    content: '',
    is_correct: false,
    feedback: '',
  }))
}

export function QuestionEditor({
  open,
  onOpenChange,
  subjects,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  subjects: Subject[]
  onSaved: () => void
}) {
  const [statement, setStatement] = useState('')
  const [subject, setSubject] = useState('')
  const [difficulty, setDifficulty] = useState<QuestionDifficulty>('MEDIUM')
  const [year, setYear] = useState('')
  const [explanation, setExplanation] = useState('')
  const [sourceNote, setSourceNote] = useState('')
  const [alternatives, setAlternatives] = useState<AlternativeInput[]>(emptyAlternatives)

  function reset() {
    setStatement('')
    setSubject('')
    setDifficulty('MEDIUM')
    setYear('')
    setExplanation('')
    setSourceNote('')
    setAlternatives(emptyAlternatives())
  }

  const save = useMutation({
    mutationFn: () =>
      adminQuestionsApi.create({
        statement: statement.trim(),
        difficulty,
        year: year ? Number(year) : null,
        explanation: explanation.trim() || null,
        source_note: sourceNote.trim() || null,
        subject_public_id: subject || null,
        alternatives: alternatives.map((item) => ({
          letter: item.letter,
          content: item.content.trim(),
          is_correct: item.is_correct,
          feedback: item.feedback?.trim() || null,
        })),
      }),
    onSuccess: () => {
      toast.success('Questão cadastrada.')
      reset()
      onOpenChange(false)
      onSaved()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.', {
        description: error instanceof ApiError ? error.fieldMessages.join(' · ') : undefined,
      }),
  })

  const correctCount = alternatives.filter((item) => item.is_correct).length
  const filled = alternatives.every((item) => item.content.trim().length > 0)
  const valid = statement.trim().length >= 10 && correctCount === 1 && filled

  function update(index: number, patch: Partial<AlternativeInput>) {
    setAlternatives((current) =>
      current.map((item, position) => (position === index ? { ...item, ...patch } : item)),
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Nova questão</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <Field label="Enunciado" htmlFor="question-statement">
            <textarea
              id="question-statement"
              rows={5}
              className="w-full rounded-md border border-border bg-surface p-3 text-sm focus-visible:outline-2 focus-visible:outline-primary"
              value={statement}
              onChange={(event) => setStatement(event.target.value)}
            />
          </Field>

          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Disciplina" htmlFor="question-subject" hint="Opcional">
              <Select
                id="question-subject"
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
              >
                <option value="">Sem disciplina</option>
                {subjects.map((item) => (
                  <option key={item.public_id} value={item.public_id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Dificuldade" htmlFor="question-difficulty">
              <Select
                id="question-difficulty"
                value={difficulty}
                onChange={(event) => setDifficulty(event.target.value as QuestionDifficulty)}
              >
                {(Object.keys(DIFFICULTY_LABEL) as QuestionDifficulty[]).map((value) => (
                  <option key={value} value={value}>
                    {DIFFICULTY_LABEL[value]}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Ano" htmlFor="question-year" hint="Opcional">
              <Input
                id="question-year"
                type="number"
                min={1990}
                max={2100}
                value={year}
                onChange={(event) => setYear(event.target.value)}
              />
            </Field>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Alternativas</p>
              {alternatives.length < LETTERS.length && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    setAlternatives((current) => [
                      ...current,
                      {
                        letter: LETTERS[current.length],
                        content: '',
                        is_correct: false,
                        feedback: '',
                      },
                    ])
                  }
                >
                  <Plus /> Alternativa
                </Button>
              )}
            </div>

            {alternatives.map((alternative, index) => (
              <div
                key={alternative.letter}
                className="space-y-2 rounded-md border border-border p-3"
              >
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{alternative.letter}</span>
                  <Input
                    aria-label={`Texto da alternativa ${alternative.letter}`}
                    value={alternative.content}
                    onChange={(event) => update(index, { content: event.target.value })}
                  />
                  <label className="flex shrink-0 items-center gap-1.5 text-xs">
                    <input
                      type="radio"
                      name="correct-alternative"
                      checked={alternative.is_correct}
                      onChange={() =>
                        setAlternatives((current) =>
                          current.map((item, position) => ({
                            ...item,
                            is_correct: position === index,
                          })),
                        )
                      }
                    />
                    gabarito
                  </label>
                  {alternatives.length > 2 && (
                    <button
                      type="button"
                      aria-label={`Remover alternativa ${alternative.letter}`}
                      className="text-subtle hover:text-danger"
                      onClick={() =>
                        setAlternatives((current) =>
                          current
                            .filter((_, position) => position !== index)
                            .map((item, position) => ({ ...item, letter: LETTERS[position] })),
                        )
                      }
                    >
                      <Trash2 className="size-4" />
                    </button>
                  )}
                </div>
                <Input
                  placeholder="Comentário desta alternativa (opcional)"
                  aria-label={`Comentário da alternativa ${alternative.letter}`}
                  value={alternative.feedback ?? ''}
                  onChange={(event) => update(index, { feedback: event.target.value })}
                />
              </div>
            ))}
          </div>

          <Field
            label="Comentário geral"
            htmlFor="question-explanation"
            hint="Aparece depois que o candidato responde."
          >
            <textarea
              id="question-explanation"
              rows={3}
              className="w-full rounded-md border border-border bg-surface p-3 text-sm focus-visible:outline-2 focus-visible:outline-primary"
              value={explanation}
              onChange={(event) => setExplanation(event.target.value)}
            />
          </Field>

          <Field
            label="Origem"
            htmlFor="question-source"
            hint="De onde veio a questão (prova, ano, órgão)."
          >
            <Input
              id="question-source"
              value={sourceNote}
              onChange={(event) => setSourceNote(event.target.value)}
            />
          </Field>

          {correctCount !== 1 && (
            <p className="text-xs text-warning">
              Marque exatamente uma alternativa como gabarito.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button loading={save.isPending} disabled={!valid} onClick={() => save.mutate()}>
            Salvar questão
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
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
import { Select } from '@/components/ui/select'
import { ApiError } from '@/lib/api/client'
import { adminQuestionsApi } from '@/lib/api/questions'
import type { ImportSummary, Subject } from '@/lib/api/types'

const EXAMPLE = `[
  {
    "statement": "Enunciado da questão…",
    "difficulty": "MEDIUM",
    "year": 2024,
    "explanation": "Comentário geral (opcional)",
    "alternatives": [
      { "letter": "A", "content": "…", "is_correct": true, "feedback": "…" },
      { "letter": "B", "content": "…", "is_correct": false }
    ]
  }
]`

export function QuestionImportDialog({
  open,
  onOpenChange,
  subjects,
  onImported,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  subjects: Subject[]
  onImported: () => void
}) {
  const [raw, setRaw] = useState('')
  const [subject, setSubject] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)
  const [summary, setSummary] = useState<ImportSummary | null>(null)

  const run = useMutation({
    mutationFn: (questions: unknown[]) =>
      adminQuestionsApi.import({ questions, subject_public_id: subject || null }),
    onSuccess: (result) => {
      setSummary(result)
      toast.success(`${result.created} questão(ões) importada(s).`)
      onImported()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Falha na importação.'),
  })

  function submit() {
    setSummary(null)
    setParseError(null)
    let parsed: unknown
    try {
      parsed = JSON.parse(raw)
    } catch (error) {
      setParseError(error instanceof Error ? error.message : 'JSON inválido.')
      return
    }
    if (!Array.isArray(parsed) || parsed.length === 0) {
      setParseError('O conteúdo precisa ser uma lista de questões.')
      return
    }
    run.mutate(parsed)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Importar questões</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-sm text-muted">
            Cole uma lista JSON com até 500 questões. Enunciados já existentes são ignorados, e
            cada questão rejeitada vem com o motivo.
          </p>

          <Field label="Disciplina do lote" htmlFor="import-subject" hint="Opcional">
            <Select
              id="import-subject"
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

          <Field label="Conteúdo JSON" htmlFor="import-json">
            <textarea
              id="import-json"
              rows={12}
              spellCheck={false}
              placeholder={EXAMPLE}
              className="w-full rounded-md border border-border bg-surface p-3 font-mono text-xs focus-visible:outline-2 focus-visible:outline-primary"
              value={raw}
              onChange={(event) => setRaw(event.target.value)}
            />
          </Field>

          {parseError && <p className="text-sm text-danger">{parseError}</p>}

          {summary && (
            <div className="space-y-2 rounded-md border border-border p-3 text-sm">
              <p>
                <strong>{summary.created}</strong> criada(s) ·{' '}
                <strong>{summary.skipped_duplicates}</strong> duplicada(s) ignorada(s) ·{' '}
                <strong>{summary.errors.length}</strong> com erro
              </p>
              {summary.errors.length > 0 && (
                <ul className="space-y-1 text-xs text-danger">
                  {summary.errors.map((error) => (
                    <li key={error}>{error}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
          <Button loading={run.isPending} disabled={raw.trim().length === 0} onClick={submit}>
            Importar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

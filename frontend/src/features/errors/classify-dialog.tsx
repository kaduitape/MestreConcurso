import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
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
import { errorsApi } from '@/lib/api/intelligence'
import { queryKeys } from '@/lib/query-client'
import { cn } from '@/lib/utils'
import type { CauseSuggestion, ErrorCause, PendingAttempt } from '@/lib/api/types'
import { CAUSE_ORDER } from '@/features/intelligence/helpers'

export function ClassifyDialog({
  attempt,
  catalogue,
  onOpenChange,
  onSaved,
}: {
  attempt: PendingAttempt | null
  catalogue: Record<string, { label: string; action: string }>
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}) {
  const [cause, setCause] = useState<ErrorCause | ''>('')
  const [trap, setTrap] = useState('')
  const [note, setNote] = useState('')
  const [suggestion, setSuggestion] = useState<CauseSuggestion | null>(null)

  useEffect(() => {
    setCause('')
    setTrap('')
    setNote('')
    setSuggestion(null)
  }, [attempt?.attempt_public_id])

  const traps = useQuery({
    queryKey: queryKeys.errorTraps,
    queryFn: () => errorsApi.traps(),
    enabled: Boolean(attempt),
  })

  const suggest = useMutation({
    mutationFn: () => errorsApi.suggestCause(attempt!.attempt_public_id),
    onSuccess: (result) => {
      setSuggestion(result)
      if (result.cause) setCause(result.cause)
      if (result.trap_slug) setTrap(result.trap_slug)
      toast.success('Sugestão recebida.', {
        description: 'Nada foi registrado ainda: confirme ou corrija a causa.',
      })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível sugerir.', {
        description:
          error instanceof ApiError && error.code === 'ai_feature_disabled'
            ? 'Configure o modelo de “error.classify” no painel de Inteligência.'
            : undefined,
      }),
  })

  const save = useMutation({
    mutationFn: () =>
      errorsApi.classify(attempt!.attempt_public_id, {
        cause: cause as ErrorCause,
        trap_slug: cause === 'TRAP' && trap ? trap : null,
        note: note.trim() || null,
      }),
    onSuccess: () => {
      toast.success('Erro registrado no caderno.')
      onOpenChange(false)
      onSaved()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível registrar.'),
  })

  const selectedAction = cause ? catalogue[cause]?.action : null

  return (
    <Dialog open={Boolean(attempt)} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Por que você errou?</DialogTitle>
        </DialogHeader>

        {attempt && (
          <div className="space-y-4">
            <div className="rounded-md border border-border p-3 text-sm">
              <p className="line-clamp-4">{attempt.question_statement}</p>
              <p className="mt-2 text-xs text-subtle">
                {attempt.subject_name ?? 'sem disciplina'}
                {attempt.selected_letter && ` · você marcou ${attempt.selected_letter}`}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                loading={suggest.isPending}
                onClick={() => suggest.mutate()}
              >
                <Sparkles /> Pedir leitura da IA
              </Button>
              <span className="text-xs text-subtle">
                A sugestão não é registrada sozinha — você confirma ou corrige.
              </span>
            </div>

            {suggestion && (
              <div className="space-y-2 rounded-md border border-secondary/40 bg-secondary-soft/30 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="info">Sugestão: {suggestion.cause_label}</Badge>
                  {suggestion.confidence !== null && (
                    <Badge variant="neutral">
                      confiança {(suggestion.confidence * 100).toFixed(0)}%
                    </Badge>
                  )}
                </div>
                {suggestion.rationale && <p className="text-muted">{suggestion.rationale}</p>}
                {suggestion.study_tip && (
                  <p className="text-muted">
                    <span className="font-medium text-foreground">O que fazer: </span>
                    {suggestion.study_tip}
                  </p>
                )}
                <p className="text-xs text-subtle">Modelo: {suggestion.model}</p>
              </div>
            )}

            <Field label="Causa" htmlFor="error-cause">
              <Select
                id="error-cause"
                value={cause}
                onChange={(event) => setCause(event.target.value as ErrorCause | '')}
              >
                <option value="">Escolha a causa</option>
                {CAUSE_ORDER.filter((value) => catalogue[value]).map((value) => (
                  <option key={value} value={value}>
                    {catalogue[value].label}
                  </option>
                ))}
              </Select>
            </Field>

            {cause === 'TRAP' && (
              <Field
                label="Qual pegadinha"
                htmlFor="error-trap"
                hint="O radar só aponta um padrão quando ele se repete."
              >
                <Select
                  id="error-trap"
                  value={trap}
                  onChange={(event) => setTrap(event.target.value)}
                >
                  <option value="">Não sei dizer</option>
                  {traps.data?.map((item) => (
                    <option key={item.slug} value={item.slug}>
                      {item.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}

            {cause === 'TRAP' && trap && (
              <p className="text-xs text-muted">
                {traps.data?.find((item) => item.slug === trap)?.detection_hint}
              </p>
            )}

            {selectedAction && (
              <p className={cn('rounded-md bg-surface-muted p-3 text-sm text-muted')}>
                <span className="font-medium text-foreground">O que isso pede: </span>
                {selectedAction}
              </p>
            )}

            <Field label="Anotação" htmlFor="error-note" hint="Opcional, só para você.">
              <textarea
                id="error-note"
                rows={3}
                className="w-full rounded-md border border-border bg-surface p-3 text-sm focus-visible:outline-2 focus-visible:outline-primary"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </Field>
          </div>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button loading={save.isPending} disabled={!cause} onClick={() => save.mutate()}>
            Registrar no caderno
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

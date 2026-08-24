import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListChecks, Plus, Search, Sparkles, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { adminCatalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { adminQuestionsApi } from '@/lib/api/questions'
import { queryKeys } from '@/lib/query-client'
import type { QuestionAdmin, QuestionDifficulty, QuestionStatus } from '@/lib/api/types'
import { DIFFICULTY_LABEL, STATUS_LABEL } from '@/features/questions/helpers'
import { QuestionEditor } from './question-editor'
import { QuestionImportDialog } from './question-import-dialog'

const STATUS_TONE: Record<QuestionStatus, 'success' | 'neutral' | 'warning' | 'outline'> = {
  PUBLISHED: 'success',
  DRAFT: 'neutral',
  NEEDS_REVIEW: 'warning',
  ARCHIVED: 'outline',
}

export function QuestionsSection() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<QuestionStatus | ''>('')
  const [editorOpen, setEditorOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [selected, setSelected] = useState<QuestionAdmin | null>(null)
  const debouncedSearch = useDebouncedValue(search, 400)

  const filters = {
    page,
    page_size: 20,
    search: debouncedSearch || undefined,
    status: status || undefined,
  }

  const questions = useQuery({
    queryKey: queryKeys.adminQuestions(filters),
    queryFn: () => adminQuestionsApi.list(filters),
    placeholderData: keepPreviousData,
  })

  const subjects = useQuery({
    queryKey: queryKeys.adminSubjects({ page: 1, page_size: 100 }),
    queryFn: () => adminCatalogApi.subjects({ page: 1, page_size: 100 }),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'questions'] })

  const remove = useMutation({
    mutationFn: (publicId: string) => adminQuestionsApi.remove(publicId),
    onSuccess: () => {
      toast.success('Questão removida.')
      setSelected(null)
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível remover.'),
  })

  const suggest = useMutation({
    mutationFn: (publicId: string) => adminQuestionsApi.suggestClassification(publicId),
    onSuccess: (suggestion) => {
      toast.success('Sugestão recebida.', {
        description: 'Nada foi aplicado: revise e confirme a classificação.',
      })
      setSelected((current) =>
        current
          ? {
              ...current,
              status: 'NEEDS_REVIEW',
              ai_suggestion: suggestion as unknown as Record<string, unknown>,
            }
          : current,
      )
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível pedir a sugestão.',
        {
          description:
            error instanceof ApiError && error.code === 'ai_feature_disabled'
              ? 'Configure o modelo de “question.classify” na aba Inteligência.'
              : undefined,
        },
      ),
  })

  const applySuggestion = useMutation({
    mutationFn: (input: {
      publicId: string
      subjectPublicId: string | null
      difficulty: QuestionDifficulty | null
    }) =>
      adminQuestionsApi.applyClassification(input.publicId, {
        subject_public_id: input.subjectPublicId,
        difficulty: input.difficulty,
      }),
    onSuccess: (question) => {
      toast.success('Classificação aplicada e questão publicada.')
      setSelected(question)
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível aplicar.'),
  })

  const suggestion = (selected?.ai_suggestion ?? {}) as {
    subject?: string
    topic?: string
    difficulty?: QuestionDifficulty
    tags?: string[]
    confidence?: number
    rationale?: string
    model?: string
    applied?: boolean
  }
  const hasSuggestion = Boolean(suggestion.subject || suggestion.difficulty)
  const suggestedSubject = subjects.data?.items.find((item) => item.name === suggestion.subject)

  return (
    <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-48 flex-1">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle"
              aria-hidden
            />
            <Input
              className="pl-9"
              placeholder="Buscar no enunciado"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPage(1)
              }}
              aria-label="Buscar no enunciado"
            />
          </div>
          <Select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as QuestionStatus | '')
              setPage(1)
            }}
            aria-label="Situação"
            className="w-auto"
          >
            <option value="">Todas as situações</option>
            {(Object.keys(STATUS_TONE) as QuestionStatus[]).map((value) => (
              <option key={value} value={value}>
                {STATUS_LABEL[value]}
              </option>
            ))}
          </Select>
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload /> Importar
          </Button>
          <Button
            onClick={() => {
              setSelected(null)
              setEditorOpen(true)
            }}
          >
            <Plus /> Nova questão
          </Button>
        </div>

        {questions.isLoading && <SkeletonList rows={4} />}
        {questions.isError && (
          <ErrorState error={questions.error} onRetry={() => questions.refetch()} />
        )}

        {questions.data?.items.length === 0 && (
          <EmptyState
            icon={ListChecks}
            title="Nenhuma questão no banco"
            description="Cadastre uma questão ou importe um lote em JSON. Questões duplicadas são detectadas pelo enunciado."
            action={
              <Button onClick={() => setEditorOpen(true)}>
                <Plus /> Cadastrar questão
              </Button>
            }
          />
        )}

        <ul className="space-y-2">
          {questions.data?.items.map((question) => (
            <li key={question.public_id}>
              <button
                type="button"
                onClick={() => setSelected(question)}
                className={`w-full rounded-md border p-3 text-left transition ${
                  selected?.public_id === question.public_id
                    ? 'border-primary bg-primary-soft/40'
                    : 'border-border hover:bg-surface-muted'
                }`}
              >
                <p className="line-clamp-2 text-sm">{question.statement}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                  <Badge variant={STATUS_TONE[question.status]}>
                    {STATUS_LABEL[question.status]}
                  </Badge>
                  <Badge variant="outline">{DIFFICULTY_LABEL[question.difficulty]}</Badge>
                  {question.subject_name ? (
                    <Badge variant="primary">{question.subject_name}</Badge>
                  ) : (
                    <span className="text-subtle">sem disciplina</span>
                  )}
                  {question.stats && (
                    <span className="text-subtle">{question.stats.attempts} respostas</span>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>

        {questions.data && questions.data.pages > 1 && (
          <div className="flex justify-between">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((value) => value - 1)}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= questions.data.pages}
              onClick={() => setPage((value) => value + 1)}
            >
              Próxima
            </Button>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{selected ? 'Questão selecionada' : 'Detalhe da questão'}</CardTitle>
          <CardDescription>
            {selected
              ? 'Gabarito, comentários e a sugestão de classificação da IA aguardando revisão.'
              : 'Escolha uma questão na lista ao lado.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!selected && (
            <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
              Nenhuma questão selecionada.
            </p>
          )}

          {selected && (
            <>
              <p className="text-sm whitespace-pre-line">{selected.statement}</p>

              <ul className="space-y-1.5 text-sm">
                {selected.alternatives.map((alternative) => (
                  <li
                    key={alternative.public_id}
                    className={`rounded-md border p-2 ${
                      alternative.is_correct
                        ? 'border-success bg-success-soft/40'
                        : 'border-border'
                    }`}
                  >
                    <span className="font-semibold">{alternative.letter}.</span>{' '}
                    {alternative.content}
                    {alternative.feedback && (
                      <p className="mt-1 text-xs text-muted">{alternative.feedback}</p>
                    )}
                  </li>
                ))}
              </ul>

              {selected.explanation && (
                <p className="rounded-md bg-surface-muted p-3 text-sm text-muted">
                  {selected.explanation}
                </p>
              )}

              <div className="rounded-md border border-border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="flex items-center gap-2 text-sm font-medium">
                    <Sparkles className="size-4 text-secondary" aria-hidden /> Classificação
                    sugerida pela IA
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    loading={suggest.isPending}
                    onClick={() => suggest.mutate(selected.public_id)}
                  >
                    Pedir sugestão
                  </Button>
                </div>

                {!hasSuggestion && (
                  <p className="mt-2 text-xs text-muted">
                    Nenhuma sugestão registrada. A sugestão nunca é aplicada sozinha: ela fica
                    aqui até alguém confirmar.
                  </p>
                )}

                {hasSuggestion && (
                  <div className="mt-3 space-y-2 text-sm">
                    <div className="flex flex-wrap gap-2">
                      {suggestion.subject && (
                        <Badge variant="info">Disciplina: {suggestion.subject}</Badge>
                      )}
                      {suggestion.topic && (
                        <Badge variant="outline">Assunto: {suggestion.topic}</Badge>
                      )}
                      {suggestion.difficulty && (
                        <Badge variant="outline">
                          {DIFFICULTY_LABEL[suggestion.difficulty]}
                        </Badge>
                      )}
                      {suggestion.confidence !== undefined && (
                        <Badge variant="neutral">
                          confiança {(suggestion.confidence * 100).toFixed(0)}%
                        </Badge>
                      )}
                    </div>
                    {suggestion.rationale && (
                      <p className="text-xs text-muted">{suggestion.rationale}</p>
                    )}
                    {suggestion.model && (
                      <p className="text-xs text-subtle">Modelo: {suggestion.model}</p>
                    )}
                    {suggestion.applied ? (
                      <Badge variant="success">Revisada e aplicada</Badge>
                    ) : (
                      <div className="flex flex-wrap items-center gap-2">
                        {!suggestedSubject && suggestion.subject && (
                          <span className="text-xs text-warning">
                            “{suggestion.subject}” não existe no catálogo: cadastre a disciplina
                            antes de aplicar.
                          </span>
                        )}
                        <Button
                          size="sm"
                          loading={applySuggestion.isPending}
                          onClick={() =>
                            applySuggestion.mutate({
                              publicId: selected.public_id,
                              subjectPublicId: suggestedSubject?.public_id ?? null,
                              difficulty: suggestion.difficulty ?? null,
                            })
                          }
                        >
                          Aplicar classificação revisada
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="flex justify-end">
                <Button
                  variant="ghost"
                  className="text-danger"
                  loading={remove.isPending}
                  onClick={() => remove.mutate(selected.public_id)}
                >
                  <Trash2 /> Remover questão
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <QuestionEditor
        open={editorOpen}
        onOpenChange={setEditorOpen}
        subjects={subjects.data?.items ?? []}
        onSaved={invalidate}
      />
      <QuestionImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        subjects={subjects.data?.items ?? []}
        onImported={invalidate}
      />
    </div>
  )
}

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Lightbulb, ListChecks, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { errorsApi } from '@/lib/api/intelligence'
import { queryKeys } from '@/lib/query-client'
import type { PendingAttempt } from '@/lib/api/types'
import { CAUSE_TONE, percent } from '@/features/intelligence/helpers'
import { ClassifyDialog } from './classify-dialog'

export function ErrorsPage() {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<PendingAttempt | null>(null)

  const notebook = useQuery({
    queryKey: queryKeys.errorNotebook,
    queryFn: () => errorsApi.notebook(),
  })
  const pending = useQuery({
    queryKey: queryKeys.errorPending,
    queryFn: () => errorsApi.pending(),
  })
  const suggested = useQuery({
    queryKey: queryKeys.errorList({ pending: true }),
    queryFn: () => errorsApi.list({ page: 1, page_size: 20, pending: true }),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['errors'] })

  const confirm = useMutation({
    mutationFn: (publicId: string) => errorsApi.confirm(publicId),
    onSuccess: () => {
      toast.success('Causa confirmada — agora ela conta no caderno.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível confirmar.'),
  })

  const data = notebook.data

  return (
    <div className="space-y-6">
      <PageHeader
        title="Meus erros"
        description="Cada erro classificado vira padrão. O caderno só conta o que você confirmou."
      />

      <Tabs defaultValue="caderno">
        <TabsList>
          <TabsTrigger value="caderno">Caderno</TabsTrigger>
          <TabsTrigger value="classificar">
            A classificar{pending.data?.length ? ` (${pending.data.length})` : ''}
          </TabsTrigger>
          <TabsTrigger value="sugestoes">
            Sugestões da IA{suggested.data?.total ? ` (${suggested.data.total})` : ''}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="caderno" className="space-y-4">
          {notebook.isLoading && <SkeletonList rows={3} />}
          {notebook.isError && (
            <ErrorState error={notebook.error} onRetry={() => notebook.refetch()} />
          )}

          {data && data.total === 0 && (
            <EmptyState
              icon={ListChecks}
              title="Nenhum erro classificado ainda"
              description={
                data.notes[0] ??
                'Classifique a causa dos seus erros para que o caderno mostre padrões.'
              }
            />
          )}

          {data && data.total > 0 && (
            <>
              {data.insights.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Lightbulb className="size-5 text-primary" aria-hidden /> O que os seus
                      erros dizem
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2 text-sm">
                      {data.insights.map((item) => (
                        <li key={item} className="flex gap-2">
                          <span className="text-primary">•</span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Por causa</CardTitle>
                    <CardDescription>
                      {data.total} erro(s) classificado(s), {data.resolved} marcado(s) como
                      superado(s).
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {data.by_cause.map((item) => (
                      <div key={item.cause} className="space-y-1.5">
                        <div className="flex items-center justify-between gap-2 text-sm">
                          <Badge variant={CAUSE_TONE[item.cause]}>{item.label}</Badge>
                          <span className="text-muted">
                            {item.count} · {percent(item.share, 0)}
                          </span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
                          <div
                            className="h-full rounded-full bg-primary"
                            style={{ width: `${item.share * 100}%` }}
                          />
                        </div>
                        <p className="text-xs text-subtle">{item.action}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <div className="space-y-4">
                  <Card>
                    <CardHeader>
                      <CardTitle>Por disciplina</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2 text-sm">
                        {data.by_subject.map((item) => (
                          <li
                            key={item.subject_name}
                            className="flex items-center justify-between gap-2 rounded-md border border-border p-2"
                          >
                            <span className="min-w-0 flex-1 truncate">{item.subject_name}</span>
                            {item.dominant_cause_label ? (
                              <Badge variant="outline">{item.dominant_cause_label}</Badge>
                            ) : (
                              <span className="text-xs text-subtle">
                                sem causa predominante
                              </span>
                            )}
                            <span className="text-muted">{item.count}</span>
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <AlertTriangle className="size-5 text-warning" aria-hidden /> Radar de
                        pegadinhas
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {data.traps.length === 0 && (
                        <p className="text-sm text-muted">
                          {data.notes.find((note) => note.toLowerCase().includes('radar')) ??
                            'Nenhum padrão repetido até aqui.'}
                        </p>
                      )}
                      {data.traps.map((item) => (
                        <div
                          key={item.slug}
                          className="flex items-center justify-between gap-2 rounded-md border border-border p-2 text-sm"
                        >
                          <span className="min-w-0 flex-1 truncate">{item.name}</span>
                          <Badge variant="danger">{item.count}×</Badge>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </div>
              </div>

              {data.notes.length > 0 && (
                <ul className="space-y-1 text-xs text-subtle">
                  {data.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </TabsContent>

        <TabsContent value="classificar" className="space-y-3">
          {pending.isLoading && <SkeletonList rows={3} />}
          {pending.data?.length === 0 && (
            <EmptyState
              icon={CheckCircle2}
              title="Nenhum erro esperando classificação"
              description="Quando você errar uma questão, ela aparece aqui para receber uma causa."
            />
          )}
          <ul className="space-y-2">
            {pending.data?.map((item) => (
              <li
                key={item.attempt_public_id}
                className="flex items-start gap-3 rounded-md border border-border p-3 text-sm"
              >
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 block">{item.question_statement}</span>
                  <span className="mt-1 block text-xs text-subtle">
                    {item.subject_name ?? 'sem disciplina'} ·{' '}
                    {new Date(item.created_at).toLocaleDateString('pt-BR')}
                    {item.selected_letter && ` · marcou ${item.selected_letter}`}
                  </span>
                </span>
                <Button size="sm" variant="outline" onClick={() => setSelected(item)}>
                  Classificar
                </Button>
              </li>
            ))}
          </ul>
        </TabsContent>

        <TabsContent value="sugestoes" className="space-y-3">
          {suggested.isLoading && <SkeletonList rows={3} />}
          {suggested.data?.items.length === 0 && (
            <EmptyState
              icon={Sparkles}
              title="Nenhuma sugestão pendente"
              description="Ao classificar um erro você pode pedir uma leitura da IA; ela fica aqui até ser confirmada."
            />
          )}
          <ul className="space-y-2">
            {suggested.data?.items.map((item) => (
              <li
                key={item.public_id}
                className="space-y-2 rounded-md border border-border p-3"
              >
                <p className="line-clamp-2 text-sm">{item.question_statement}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={CAUSE_TONE[item.cause]}>{item.cause_label}</Badge>
                  <Badge variant="info">sugerida pela IA</Badge>
                  {item.model_slug && (
                    <span className="text-xs text-subtle">{item.model_slug}</span>
                  )}
                </div>
                {item.rationale && <p className="text-sm text-muted">{item.rationale}</p>}
                <p className="text-xs text-subtle">
                  Enquanto não for confirmada, não entra em nenhuma estatística do caderno.
                </p>
                <Button
                  size="sm"
                  loading={confirm.isPending}
                  onClick={() => confirm.mutate(item.public_id)}
                >
                  Confirmar causa
                </Button>
              </li>
            ))}
          </ul>
        </TabsContent>
      </Tabs>

      <ClassifyDialog
        attempt={selected}
        catalogue={data?.causes_catalogue ?? {}}
        onOpenChange={(open) => !open && setSelected(null)}
        onSaved={invalidate}
      />
    </div>
  )
}

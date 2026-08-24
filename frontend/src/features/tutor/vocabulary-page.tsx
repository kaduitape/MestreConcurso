import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookMarked, FileText, Plus, Search, Sparkles, Trash2 } from 'lucide-react'
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
import { Input } from '@/components/ui/input'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { ApiError } from '@/lib/api/client'
import { vocabularyApi } from '@/lib/api/tutor'
import { queryKeys } from '@/lib/query-client'

export function VocabularyPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ term: '', definition: '' })
  const debouncedSearch = useDebouncedValue(search, 400)

  const params = { page, page_size: 20, search: debouncedSearch || undefined }
  const terms = useQuery({
    queryKey: queryKeys.vocabulary(params),
    queryFn: () => vocabularyApi.list(params),
    placeholderData: keepPreviousData,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['vocabulary'] })

  const create = useMutation({
    mutationFn: () => vocabularyApi.add({ term: form.term, definition: form.definition }),
    onSuccess: () => {
      toast.success('Termo guardado.')
      setForm({ term: '', definition: '' })
      setOpen(false)
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível guardar.'),
  })

  const review = useMutation({
    mutationFn: (publicId: string) => vocabularyApi.review(publicId),
    onSuccess: () => invalidate(),
  })

  const remove = useMutation({
    mutationFn: (publicId: string) => vocabularyApi.remove(publicId),
    onSuccess: () => {
      toast.success('Termo removido.')
      invalidate()
    },
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Vocabulário"
        description="Os termos que você guardou das conversas, com a origem de cada definição."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus /> Novo termo
          </Button>
        }
      />

      <div className="relative max-w-md">
        <Search
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle"
          aria-hidden
        />
        <Input
          className="pl-9"
          placeholder="Buscar termo"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(1)
          }}
          aria-label="Buscar termo"
        />
      </div>

      {terms.isLoading && <SkeletonList rows={4} />}
      {terms.isError && <ErrorState error={terms.error} onRetry={() => terms.refetch()} />}

      {terms.data?.items.length === 0 && (
        <EmptyState
          icon={BookMarked}
          title="Nenhum termo guardado"
          description="Ao conversar com o Mestre, guarde os termos que aparecerem. Quando vierem de um trecho citado, a origem vem junto."
        />
      )}

      <ul className="grid gap-3 md:grid-cols-2">
        {terms.data?.items.map((entry) => (
          <li key={entry.public_id} className="space-y-2 rounded-lg border border-border p-4">
            <div className="flex items-start justify-between gap-2">
              <p className="font-medium">{entry.term}</p>
              <Badge variant={entry.origin === 'CITED' ? 'success' : 'info'}>
                {entry.origin === 'CITED' ? (
                  <>
                    <FileText className="size-3" aria-hidden /> do documento
                  </>
                ) : (
                  <>
                    <Sparkles className="size-3" aria-hidden /> redigido por IA
                  </>
                )}
              </Badge>
            </div>
            <p className="text-sm text-muted">{entry.definition}</p>

            {entry.origin === 'CITED' && entry.source_quote && (
              <p className="rounded-md bg-surface-muted p-2 text-xs text-muted italic">
                “{entry.source_quote}”
                {entry.source_document && (
                  <span className="mt-1 block not-italic text-subtle">
                    {entry.source_document}
                    {entry.source_page !== null && `, p. ${entry.source_page}`}
                  </span>
                )}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-2 text-xs text-subtle">
              {entry.subject_name && <Badge variant="outline">{entry.subject_name}</Badge>}
              <span>{entry.times_reviewed} revisão(ões)</span>
              <Button
                size="sm"
                variant="ghost"
                className="ml-auto"
                onClick={() => review.mutate(entry.public_id)}
              >
                Revisei
              </Button>
              <button
                type="button"
                aria-label={`Remover ${entry.term}`}
                className="text-subtle hover:text-danger"
                onClick={() => remove.mutate(entry.public_id)}
              >
                <Trash2 className="size-4" />
              </button>
            </div>
          </li>
        ))}
      </ul>

      {terms.data && terms.data.pages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((value) => value - 1)}
          >
            Anterior
          </Button>
          <span>
            Página {terms.data.page} de {terms.data.pages} · {terms.data.total} termos
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= terms.data.pages}
            onClick={() => setPage((value) => value + 1)}
          >
            Próxima
          </Button>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Novo termo</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Field label="Termo" htmlFor="vocab-term">
              <Input
                id="vocab-term"
                value={form.term}
                onChange={(event) => setForm({ ...form, term: event.target.value })}
              />
            </Field>
            <Field
              label="Definição"
              htmlFor="vocab-definition"
              hint="Termo criado aqui fica marcado como redação sua, não como texto do edital."
            >
              <textarea
                id="vocab-definition"
                rows={4}
                className="w-full rounded-md border border-border bg-surface p-3 text-sm focus-visible:outline-2 focus-visible:outline-primary"
                value={form.definition}
                onChange={(event) => setForm({ ...form, definition: event.target.value })}
              />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              loading={create.isPending}
              disabled={form.term.trim().length < 2 || form.definition.trim().length < 2}
              onClick={() => create.mutate()}
            >
              Guardar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

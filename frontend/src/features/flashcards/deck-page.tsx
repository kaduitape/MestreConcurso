import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Layers, Plus, Search, Sparkles, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
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
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { catalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { flashcardsApi, reviewApi } from '@/lib/api/flashcards'
import { queryKeys } from '@/lib/query-client'
import type { CardOrigin } from '@/lib/api/types'
import { GenerateDialog } from './generate-dialog'
import { ORIGIN_LABEL, ORIGIN_TONE } from './helpers'

export function DeckPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [origin, setOrigin] = useState<CardOrigin | ''>('')
  const [open, setOpen] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [form, setForm] = useState({ front: '', back: '', hint: '', subject: '' })
  const debouncedSearch = useDebouncedValue(search, 400)

  const params = {
    page,
    page_size: 20,
    search: debouncedSearch || undefined,
    origin: origin || undefined,
  }
  const cards = useQuery({
    queryKey: queryKeys.flashcards(params),
    queryFn: () => flashcardsApi.list(params),
    placeholderData: keepPreviousData,
  })

  const stats = useQuery({
    queryKey: queryKeys.reviewStats,
    queryFn: () => reviewApi.stats(),
  })

  const subjects = useQuery({
    queryKey: ['catalog', 'subjects', 'all'],
    queryFn: () => catalogApi.subjects({ page: 1, page_size: 100 }),
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['flashcards'] })
    queryClient.invalidateQueries({ queryKey: ['review'] })
  }

  const create = useMutation({
    mutationFn: () =>
      flashcardsApi.create({
        front: form.front,
        back: form.back,
        hint: form.hint || null,
        subject_public_id: form.subject || null,
      }),
    onSuccess: () => {
      toast.success('Cartão criado.')
      setForm({ front: '', back: '', hint: '', subject: '' })
      setOpen(false)
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível criar.'),
  })

  const remove = useMutation({
    mutationFn: (publicId: string) => flashcardsApi.remove(publicId),
    onSuccess: () => {
      toast.success('Cartão removido.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível remover.'),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Flashcards"
        description="Seu baralho e o estado da sua memória. Cada cartão carrega de onde veio."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setGenerating(true)}>
              <Sparkles /> Gerar com IA
            </Button>
            <Button onClick={() => setOpen(true)}>
              <Plus /> Novo cartão
            </Button>
          </div>
        }
      />

      {stats.data && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted">No baralho</p>
              <p className="text-3xl font-semibold">{stats.data.total_cards}</p>
              <p className="mt-1 text-xs text-subtle">
                {stats.data.mature_cards} já consolidado(s)
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted">Vencendo hoje</p>
              <p className="text-3xl font-semibold">{stats.data.due_today}</p>
              <p className="mt-1 text-xs text-subtle">
                {stats.data.reviewed_today} revisado(s) hoje
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted">Taxa de recordação</p>
              <p className="text-3xl font-semibold">
                {stats.data.recall_rate === null
                  ? '—'
                  : `${(stats.data.recall_rate * 100).toFixed(0)}%`}
              </p>
              <p className="mt-1 text-xs text-subtle">
                {stats.data.recall_rate === null
                  ? 'sem revisões registradas ainda'
                  : `em ${stats.data.total_reviews} revisões`}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted">Próximos 14 dias</p>
              <div className="mt-2 flex h-12 items-end gap-0.5">
                {stats.data.upcoming.map((day) => {
                  const peak = Math.max(...stats.data!.upcoming.map((item) => item.count), 1)
                  return (
                    <span
                      key={day.day}
                      title={`${day.day}: ${day.count}`}
                      className="flex-1 rounded-sm bg-primary/70"
                      style={{ height: `${Math.max(4, (day.count / peak) * 100)}%` }}
                    />
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle"
            aria-hidden
          />
          <Input
            className="pl-9"
            placeholder="Buscar na frente ou no verso"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
            aria-label="Buscar cartão"
          />
        </div>
        <Select
          value={origin}
          onChange={(event) => {
            setOrigin(event.target.value as CardOrigin | '')
            setPage(1)
          }}
          aria-label="Origem"
        >
          <option value="">Todas as origens</option>
          {(Object.keys(ORIGIN_LABEL) as CardOrigin[]).map((value) => (
            <option key={value} value={value}>
              {ORIGIN_LABEL[value]}
            </option>
          ))}
        </Select>
      </div>

      {cards.isLoading && <SkeletonList rows={4} />}
      {cards.isError && <ErrorState error={cards.error} onRetry={() => cards.refetch()} />}

      {cards.data?.items.length === 0 && (
        <EmptyState
          icon={Layers}
          title="Nenhum cartão no baralho"
          description="Crie cartões à mão, gere a partir de um material ou transforme suas questões erradas em cartões."
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus /> Criar o primeiro
            </Button>
          }
        />
      )}

      <ul className="grid gap-3 md:grid-cols-2">
        {cards.data?.items.map((card) => (
          <li key={card.public_id} className="space-y-2 rounded-lg border border-border p-4">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium">{card.front}</p>
              <Badge variant={ORIGIN_TONE[card.origin]}>{ORIGIN_LABEL[card.origin]}</Badge>
            </div>
            <p className="text-sm text-muted">{card.back}</p>

            {card.source_quote && (
              <p className="rounded-md bg-surface-muted p-2 text-xs text-muted italic">
                “{card.source_quote}”
                {card.source_document && (
                  <span className="mt-1 block not-italic text-subtle">
                    {card.source_document}
                    {card.source_page !== null && `, p. ${card.source_page}`}
                  </span>
                )}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-2 text-xs text-subtle">
              {card.subject_name && <Badge variant="outline">{card.subject_name}</Badge>}
              {card.model_slug && <span>{card.model_slug}</span>}
              {card.is_owned && (
                <button
                  type="button"
                  aria-label="Remover cartão"
                  className="ml-auto text-subtle hover:text-danger"
                  onClick={() => remove.mutate(card.public_id)}
                >
                  <Trash2 className="size-4" />
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>

      {cards.data && cards.data.pages > 1 && (
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
            Página {cards.data.page} de {cards.data.pages} · {cards.data.total} cartões
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= cards.data.pages}
            onClick={() => setPage((value) => value + 1)}
          >
            Próxima
          </Button>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Novo cartão</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Field
              label="Frente"
              htmlFor="card-front"
              hint="Uma pergunta objetiva. A frente nunca deve conter a resposta."
            >
              <textarea
                id="card-front"
                rows={3}
                className="w-full rounded-md border border-border bg-surface p-3 text-sm focus-visible:outline-2 focus-visible:outline-primary"
                value={form.front}
                onChange={(event) => setForm({ ...form, front: event.target.value })}
              />
            </Field>
            <Field label="Verso" htmlFor="card-back" hint="Uma resposta curta.">
              <textarea
                id="card-back"
                rows={3}
                className="w-full rounded-md border border-border bg-surface p-3 text-sm focus-visible:outline-2 focus-visible:outline-primary"
                value={form.back}
                onChange={(event) => setForm({ ...form, back: event.target.value })}
              />
            </Field>
            <Field label="Pista" htmlFor="card-hint" hint="Opcional">
              <Input
                id="card-hint"
                value={form.hint}
                onChange={(event) => setForm({ ...form, hint: event.target.value })}
              />
            </Field>
            <Field label="Disciplina" htmlFor="card-subject" hint="Opcional">
              <Select
                id="card-subject"
                value={form.subject}
                onChange={(event) => setForm({ ...form, subject: event.target.value })}
              >
                <option value="">Sem disciplina</option>
                {subjects.data?.items.map((item) => (
                  <option key={item.public_id} value={item.public_id}>
                    {item.name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              loading={create.isPending}
              disabled={form.front.trim().length < 3 || form.back.trim().length < 1}
              onClick={() => create.mutate()}
            >
              Criar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <GenerateDialog open={generating} onOpenChange={setGenerating} onGenerated={invalidate} />
    </div>
  )
}

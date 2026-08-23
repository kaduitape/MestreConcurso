import { useRef, useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, ChevronRight, Plus, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { adminCatalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/query-client'
import type { Subject } from '@/lib/api/types'

const COLOR_TOKENS = [
  ['subject-portugues', 'Português'],
  ['subject-direito', 'Direito'],
  ['subject-raciocinio', 'Raciocínio/Exatas'],
  ['subject-informatica', 'Informática'],
  ['subject-atualidades', 'Atualidades'],
  ['subject-especifica', 'Específica'],
] as const

export function SubjectsSection() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<Subject | null>(null)
  const [topicName, setTopicName] = useState('')
  const [parentId, setParentId] = useState('')
  const [form, setForm] = useState({ name: '', area: '', color_token: 'subject-especifica' })
  const fileInput = useRef<HTMLInputElement>(null)

  const params = { page, page_size: 20 }
  const subjects = useQuery({
    queryKey: queryKeys.adminSubjects(params),
    queryFn: () => adminCatalogApi.subjects(params),
    placeholderData: keepPreviousData,
  })

  const topics = useQuery({
    queryKey: queryKeys.adminTopics(selected?.public_id ?? ''),
    queryFn: () => adminCatalogApi.topics(selected!.public_id),
    enabled: Boolean(selected),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] })

  const createSubject = useMutation({
    mutationFn: () =>
      adminCatalogApi.createSubject({
        name: form.name,
        area: form.area || null,
        color_token: form.color_token,
      }),
    onSuccess: () => {
      toast.success('Disciplina cadastrada.')
      setOpen(false)
      setForm({ name: '', area: '', color_token: 'subject-especifica' })
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  const createTopic = useMutation({
    mutationFn: () =>
      adminCatalogApi.createTopic(selected!.public_id, {
        name: topicName,
        parent_public_id: parentId || null,
      }),
    onSuccess: () => {
      setTopicName('')
      toast.success('Assunto adicionado.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível adicionar.'),
  })

  const deleteTopic = useMutation({
    mutationFn: (publicId: string) => adminCatalogApi.deleteTopic(publicId),
    onSuccess: () => {
      toast.success('Assunto removido (subassuntos incluídos).')
      invalidate()
    },
  })

  const importTopics = useMutation({
    mutationFn: (file: File) => adminCatalogApi.importTopics(selected!.public_id, file),
    onSuccess: (result) => {
      toast.success(
        `${result.created} assunto(s) importado(s), ${result.skipped} ignorado(s).`,
        { description: result.errors[0] },
      )
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Falha na importação.'),
  })

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
      <div className="space-y-4">
        <div className="flex justify-end">
          <Button onClick={() => setOpen(true)}>
            <Plus /> Nova disciplina
          </Button>
        </div>

        {subjects.isLoading && <SkeletonList rows={3} />}
        {subjects.isError && (
          <ErrorState error={subjects.error} onRetry={() => subjects.refetch()} />
        )}

        {subjects.data?.items.length === 0 && (
          <EmptyState
            icon={BookOpen}
            title="Nenhuma disciplina"
            description="As disciplinas são canônicas: um mesmo “Direito Penal” serve a todos os concursos."
            action={
              <Button onClick={() => setOpen(true)}>
                <Plus /> Cadastrar disciplina
              </Button>
            }
          />
        )}

        <ul className="space-y-2">
          {subjects.data?.items.map((subject) => (
            <li key={subject.public_id}>
              <button
                type="button"
                onClick={() => setSelected(subject)}
                className={`flex w-full items-center gap-3 rounded-md border p-3 text-left transition ${
                  selected?.public_id === subject.public_id
                    ? 'border-primary bg-primary-soft/40'
                    : 'border-border hover:bg-surface-muted'
                }`}
              >
                <span
                  className="size-3 shrink-0 rounded-full"
                  style={{ backgroundColor: `var(--${subject.color_token})` }}
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{subject.name}</span>
                  <span className="block truncate text-xs text-muted">
                    {subject.area ?? 'sem área'}
                  </span>
                </span>
                <ChevronRight className="size-4 text-subtle" aria-hidden />
              </button>
            </li>
          ))}
        </ul>

        {subjects.data && subjects.data.pages > 1 && (
          <div className="flex justify-between text-sm text-muted">
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
              disabled={page >= subjects.data.pages}
              onClick={() => setPage((value) => value + 1)}
            >
              Próxima
            </Button>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            {selected ? `Assuntos de ${selected.name}` : 'Árvore de assuntos'}
          </CardTitle>
          <CardDescription>
            {selected
              ? 'Até 4 níveis. É esta árvore que sustenta o mapa de incidência e o Priority Score nas fases seguintes.'
              : 'Escolha uma disciplina ao lado para editar seus assuntos.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!selected && (
            <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
              Nenhuma disciplina selecionada.
            </p>
          )}

          {selected && (
            <>
              <form
                className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]"
                onSubmit={(event) => {
                  event.preventDefault()
                  createTopic.mutate()
                }}
              >
                <Input
                  placeholder="Nome do assunto"
                  value={topicName}
                  onChange={(event) => setTopicName(event.target.value)}
                  aria-label="Nome do assunto"
                />
                <Select
                  value={parentId}
                  onChange={(event) => setParentId(event.target.value)}
                  aria-label="Assunto pai"
                >
                  <option value="">nível principal</option>
                  {topics.data
                    ?.filter((topic) => topic.depth < 3)
                    .map((topic) => (
                      <option key={topic.public_id} value={topic.public_id}>
                        {'— '.repeat(topic.depth)}
                        {topic.name}
                      </option>
                    ))}
                </Select>
                <Button
                  type="submit"
                  loading={createTopic.isPending}
                  disabled={topicName.trim().length < 2}
                >
                  <Plus />
                </Button>
              </form>

              <div className="flex flex-wrap items-center gap-2">
                <input
                  ref={fileInput}
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (file) importTopics.mutate(file)
                    event.target.value = ''
                  }}
                />
                <Button
                  variant="outline"
                  size="sm"
                  loading={importTopics.isPending}
                  onClick={() => fileInput.current?.click()}
                >
                  <Upload /> Importar CSV
                </Button>
                <span className="text-xs text-subtle">
                  Formato: <code>assunto;subassunto;ordem</code>
                </span>
              </div>

              {topics.isLoading && <SkeletonList rows={3} />}

              {topics.data?.length === 0 && (
                <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
                  Nenhum assunto cadastrado nesta disciplina.
                </p>
              )}

              <ul className="max-h-96 space-y-1 overflow-y-auto">
                {topics.data?.map((topic) => (
                  <li
                    key={topic.public_id}
                    className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-surface-muted"
                    style={{ paddingLeft: `${topic.depth * 20 + 8}px` }}
                  >
                    <span className="min-w-0 flex-1 truncate">{topic.name}</span>
                    {topic.depth > 0 && (
                      <Badge variant="outline">nível {topic.depth + 1}</Badge>
                    )}
                    <button
                      type="button"
                      className="text-subtle hover:text-danger"
                      aria-label={`Remover ${topic.name}`}
                      onClick={() => deleteTopic.mutate(topic.public_id)}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nova disciplina</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Field label="Nome" htmlFor="subject-name">
              <Input
                id="subject-name"
                placeholder="Direito Constitucional"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Field>
            <Field label="Área" htmlFor="subject-area" hint="Opcional">
              <Input
                id="subject-area"
                placeholder="Direito"
                value={form.area}
                onChange={(event) => setForm({ ...form, area: event.target.value })}
              />
            </Field>
            <Field
              label="Cor"
              htmlFor="subject-color"
              hint="A cor acompanha a disciplina em todas as telas."
            >
              <Select
                id="subject-color"
                value={form.color_token}
                onChange={(event) => setForm({ ...form, color_token: event.target.value })}
              >
                {COLOR_TOKENS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
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
              loading={createSubject.isPending}
              disabled={form.name.trim().length < 2}
              onClick={() => createSubject.mutate()}
            >
              Salvar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

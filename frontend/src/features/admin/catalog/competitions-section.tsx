import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Briefcase, Eye, EyeOff, Plus, Search, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Table, TableWrapper, Td, Th, Tr } from '@/components/ui/table'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { adminCatalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/query-client'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { STATUS_LABEL, formatCurrency, formatDate } from './helpers'
import { CompetitionDialog } from './competition-dialog'

export function CompetitionsSection() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [detailId, setDetailId] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '',
    year: String(new Date().getFullYear()),
    organization_public_id: '',
    exam_board_public_id: '',
    status: 'ANNOUNCED',
    exam_date: '',
    vacancies_total: '',
  })

  const debounced = useDebouncedValue(search, 350)
  const params = { page, page_size: 20, search: debounced }
  const query = useQuery({
    queryKey: queryKeys.adminCompetitions(params),
    queryFn: () => adminCatalogApi.competitions(params),
    placeholderData: keepPreviousData,
  })
  const organizations = useQuery({
    queryKey: queryKeys.adminOrganizations({ page: 1, page_size: 100 }),
    queryFn: () => adminCatalogApi.organizations({ page: 1, page_size: 100 }),
    enabled: open,
  })
  const boards = useQuery({
    queryKey: queryKeys.adminBoards({ page: 1, page_size: 100 }),
    queryFn: () => adminCatalogApi.boards({ page: 1, page_size: 100 }),
    enabled: open,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] })

  const create = useMutation({
    mutationFn: () =>
      adminCatalogApi.createCompetition({
        name: form.name,
        year: Number(form.year),
        organization_public_id: form.organization_public_id,
        exam_board_public_id: form.exam_board_public_id || null,
        status: form.status,
        exam_date: form.exam_date || null,
        vacancies_total: form.vacancies_total ? Number(form.vacancies_total) : null,
      }),
    onSuccess: (competition) => {
      toast.success('Concurso cadastrado.')
      setOpen(false)
      setDetailId(competition.public_id)
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  const togglePublished = useMutation({
    mutationFn: (input: { publicId: string; value: boolean }) =>
      adminCatalogApi.updateCompetition(input.publicId, { is_published: input.value }),
    onSuccess: (competition) => {
      toast.success(
        competition.is_published
          ? 'Concurso publicado para os candidatos.'
          : 'Concurso despublicado.',
      )
      invalidate()
    },
  })

  const remove = useMutation({
    mutationFn: (publicId: string) => adminCatalogApi.deleteCompetition(publicId),
    onSuccess: () => {
      toast.success('Concurso removido.')
      invalidate()
    },
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-64 flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle"
            aria-hidden
          />
          <Input
            className="pl-9"
            placeholder="Buscar concurso"
            value={search}
            onChange={(event) => {
              setPage(1)
              setSearch(event.target.value)
            }}
            aria-label="Buscar concursos"
          />
        </div>
        <Button onClick={() => setOpen(true)}>
          <Plus /> Novo concurso
        </Button>
      </div>

      {query.isLoading && <SkeletonList rows={3} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.data?.items.length === 0 && (
        <EmptyState
          icon={Briefcase}
          title="Nenhum concurso cadastrado"
          description="Cadastre um concurso, adicione os cargos e vincule as disciplinas cobradas."
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus /> Cadastrar concurso
            </Button>
          }
        />
      )}

      {query.data && query.data.items.length > 0 && (
        <>
          <TableWrapper>
            <Table>
              <thead>
                <tr>
                  <Th>Concurso</Th>
                  <Th>Banca</Th>
                  <Th>Prova</Th>
                  <Th>Vagas</Th>
                  <Th>Situação</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((competition) => (
                  <Tr key={competition.public_id}>
                    <Td>
                      <button
                        type="button"
                        className="text-left font-medium hover:text-primary"
                        onClick={() => setDetailId(competition.public_id)}
                      >
                        {competition.name}
                      </button>
                      <p className="text-xs text-muted">
                        {competition.organization.short_name} · {competition.year}
                      </p>
                    </Td>
                    <Td className="text-sm">{competition.exam_board?.short_name ?? '—'}</Td>
                    <Td className="text-sm text-muted">{formatDate(competition.exam_date)}</Td>
                    <Td className="text-sm tabular-nums">
                      {competition.vacancies_total?.toLocaleString('pt-BR') ?? '—'}
                    </Td>
                    <Td className="space-x-1">
                      <Badge variant="outline">{STATUS_LABEL[competition.status]}</Badge>
                      {competition.is_published ? (
                        <Badge variant="success">Publicado</Badge>
                      ) : (
                        <Badge variant="neutral">Rascunho</Badge>
                      )}
                    </Td>
                    <Td className="text-right whitespace-nowrap">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          togglePublished.mutate({
                            publicId: competition.public_id,
                            value: !competition.is_published,
                          })
                        }
                        title={
                          competition.is_published
                            ? 'Ocultar dos candidatos'
                            : 'Publicar para os candidatos'
                        }
                      >
                        {competition.is_published ? <EyeOff /> : <Eye />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-danger"
                        loading={remove.isPending && remove.variables === competition.public_id}
                        onClick={() => remove.mutate(competition.public_id)}
                      >
                        <Trash2 />
                      </Button>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrapper>

          <div className="flex items-center justify-between text-sm text-muted">
            <span>
              {query.data.total} concurso(s) · página {query.data.page} de {query.data.pages}
            </span>
            <div className="flex gap-2">
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
                disabled={page >= query.data.pages}
                onClick={() => setPage((value) => value + 1)}
              >
                Próxima
              </Button>
            </div>
          </div>
        </>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Novo concurso</DialogTitle>
            <DialogDescription>
              Cadastre o certame; os cargos e disciplinas são adicionados em seguida.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Field label="Nome" htmlFor="comp-name">
              <Input
                id="comp-name"
                placeholder="PCDF 2026 — Agente de Polícia"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Órgão" htmlFor="comp-org">
                <Select
                  id="comp-org"
                  value={form.organization_public_id}
                  onChange={(event) =>
                    setForm({ ...form, organization_public_id: event.target.value })
                  }
                >
                  <option value="">selecione</option>
                  {organizations.data?.items.map((organization) => (
                    <option key={organization.public_id} value={organization.public_id}>
                      {organization.short_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Banca" htmlFor="comp-board" hint="Pode ser definida depois">
                <Select
                  id="comp-board"
                  value={form.exam_board_public_id}
                  onChange={(event) =>
                    setForm({ ...form, exam_board_public_id: event.target.value })
                  }
                >
                  <option value="">não definida</option>
                  {boards.data?.items.map((board) => (
                    <option key={board.public_id} value={board.public_id}>
                      {board.short_name}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Ano" htmlFor="comp-year">
                <Input
                  id="comp-year"
                  type="number"
                  value={form.year}
                  onChange={(event) => setForm({ ...form, year: event.target.value })}
                />
              </Field>
              <Field label="Situação" htmlFor="comp-status">
                <Select
                  id="comp-status"
                  value={form.status}
                  onChange={(event) => setForm({ ...form, status: event.target.value })}
                >
                  {Object.entries(STATUS_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Data da prova" htmlFor="comp-date" hint="Opcional">
                <Input
                  id="comp-date"
                  type="date"
                  value={form.exam_date}
                  onChange={(event) => setForm({ ...form, exam_date: event.target.value })}
                />
              </Field>
            </div>
            <Field label="Vagas" htmlFor="comp-vacancies" hint="Opcional">
              <Input
                id="comp-vacancies"
                type="number"
                value={form.vacancies_total}
                onChange={(event) => setForm({ ...form, vacancies_total: event.target.value })}
              />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              loading={create.isPending}
              disabled={form.name.trim().length < 3 || !form.organization_public_id}
              onClick={() => create.mutate()}
            >
              Salvar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <CompetitionDialog publicId={detailId} onClose={() => setDetailId(null)} />
      <p className="text-xs text-subtle">
        Concursos em rascunho ficam invisíveis para os candidatos. Publique quando as
        informações estiverem conferidas — {formatCurrency(null)} indica dado ainda não
        informado.
      </p>
    </div>
  )
}

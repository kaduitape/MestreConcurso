import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Brain, Landmark, Pencil, Plus, Trash2 } from 'lucide-react'
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
import { Table, TableWrapper, Td, Th, Tr } from '@/components/ui/table'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { adminCatalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/query-client'
import type { ExamBoard } from '@/lib/api/types'
import { BoardKnowledgeDialog } from './board-knowledge-dialog'

export function BoardsSection() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<ExamBoard | null>(null)
  const [creating, setCreating] = useState(false)
  const [knowledgeBoard, setKnowledgeBoard] = useState<ExamBoard | null>(null)
  const [form, setForm] = useState({ name: '', short_name: '', website: '' })

  const params = { page, page_size: 20 }
  const query = useQuery({
    queryKey: queryKeys.adminBoards(params),
    queryFn: () => adminCatalogApi.boards(params),
    placeholderData: keepPreviousData,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] })

  const save = useMutation({
    mutationFn: () =>
      editing
        ? adminCatalogApi.updateBoard(editing.public_id, {
            name: form.name,
            short_name: form.short_name,
            website: form.website || null,
          })
        : adminCatalogApi.createBoard({
            name: form.name,
            short_name: form.short_name,
            website: form.website || null,
          }),
    onSuccess: () => {
      toast.success(editing ? 'Banca atualizada.' : 'Banca cadastrada.')
      setEditing(null)
      setCreating(false)
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  const remove = useMutation({
    mutationFn: (publicId: string) => adminCatalogApi.deleteBoard(publicId),
    onSuccess: () => {
      toast.success('Banca removida.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível remover.'),
  })

  const openCreate = () => {
    setForm({ name: '', short_name: '', website: '' })
    setEditing(null)
    setCreating(true)
  }

  const openEdit = (board: ExamBoard) => {
    setForm({
      name: board.name,
      short_name: board.short_name,
      website: board.website ?? '',
    })
    setEditing(board)
    setCreating(true)
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={openCreate}>
          <Plus /> Nova banca
        </Button>
      </div>

      {query.isLoading && <SkeletonList rows={3} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.data?.items.length === 0 && (
        <EmptyState
          icon={Landmark}
          title="Nenhuma banca cadastrada"
          description="Cadastre as bancas organizadoras para vincular concursos e, nas próximas fases, o perfil de cada uma."
          action={
            <Button onClick={openCreate}>
              <Plus /> Cadastrar banca
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
                  <Th>Banca</Th>
                  <Th>Identificador</Th>
                  <Th>Site</Th>
                  <Th>Status</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((board) => (
                  <Tr key={board.public_id}>
                    <Td>
                      <p className="font-medium">{board.short_name}</p>
                      <p className="text-xs text-muted">{board.name}</p>
                    </Td>
                    <Td className="font-mono text-xs text-muted">{board.slug}</Td>
                    <Td className="text-sm text-muted">{board.website ?? '—'}</Td>
                    <Td>
                      <Badge variant={board.is_active ? 'success' : 'neutral'}>
                        {board.is_active ? 'Ativa' : 'Inativa'}
                      </Badge>
                    </Td>
                    <Td className="text-right whitespace-nowrap">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setKnowledgeBoard(board)}
                        title="Conhecimento acumulado sobre a banca"
                      >
                        <Brain /> Conhecimento
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => openEdit(board)}>
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-danger"
                        loading={remove.isPending && remove.variables === board.public_id}
                        onClick={() => remove.mutate(board.public_id)}
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
              {query.data.total} banca(s) · página {query.data.page} de {query.data.pages}
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

      <Dialog open={creating} onOpenChange={(open) => !open && setCreating(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? 'Editar banca' : 'Nova banca'}</DialogTitle>
            <DialogDescription>
              O identificador é gerado a partir da sigla e usado nas URLs.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Field label="Sigla" htmlFor="board-short">
              <Input
                id="board-short"
                placeholder="CESPE"
                value={form.short_name}
                onChange={(event) => setForm({ ...form, short_name: event.target.value })}
              />
            </Field>
            <Field label="Nome completo" htmlFor="board-name">
              <Input
                id="board-name"
                placeholder="Cebraspe"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Field>
            <Field label="Site" htmlFor="board-site" hint="Opcional">
              <Input
                id="board-site"
                placeholder="https://"
                value={form.website}
                onChange={(event) => setForm({ ...form, website: event.target.value })}
              />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreating(false)}>
              Cancelar
            </Button>
            <Button
              loading={save.isPending}
              disabled={form.name.trim().length < 2 || form.short_name.trim().length < 2}
              onClick={() => save.mutate()}
            >
              Salvar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <BoardKnowledgeDialog board={knowledgeBoard} onClose={() => setKnowledgeBoard(null)} />
    </div>
  )
}

import { useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { Search, Settings2, Users } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableWrapper, Td, Th, Tr } from '@/components/ui/table'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { adminApi } from '@/lib/api/admin'
import { queryKeys } from '@/lib/query-client'
import type { User } from '@/lib/api/types'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { UserEditDialog } from './user-edit-dialog'
import { useAuth } from '@/providers/auth-provider'

const statusVariant = {
  ACTIVE: 'success',
  PENDING: 'warning',
  SUSPENDED: 'danger',
  DELETED: 'neutral',
} as const

const statusLabel = {
  ACTIVE: 'Ativo',
  PENDING: 'Pendente',
  SUSPENDED: 'Suspenso',
  DELETED: 'Excluído',
} as const

const columnHelper = createColumnHelper<User>()

export function UsersSection() {
  const { hasPermission } = useAuth()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [editing, setEditing] = useState<User | null>(null)
  const debouncedSearch = useDebouncedValue(search, 350)

  const params = { page, page_size: 20, search: debouncedSearch, status }
  const query = useQuery({
    queryKey: queryKeys.adminUsers(params),
    queryFn: () => adminApi.users(params),
    placeholderData: keepPreviousData,
  })

  const columns = useMemo(
    () => [
      columnHelper.accessor('full_name', {
        header: 'Usuário',
        cell: (info) => (
          <div className="min-w-0">
            <p className="truncate font-medium">{info.getValue()}</p>
            <p className="truncate text-xs text-muted">{info.row.original.email}</p>
          </div>
        ),
      }),
      columnHelper.accessor('status', {
        header: 'Status',
        cell: (info) => (
          <Badge variant={statusVariant[info.getValue()]}>{statusLabel[info.getValue()]}</Badge>
        ),
      }),
      columnHelper.accessor('roles', {
        header: 'Papéis',
        cell: (info) => (
          <div className="flex flex-wrap gap-1">
            {info.getValue().map((role) => (
              <Badge key={role.slug} variant="outline">
                {role.name}
              </Badge>
            ))}
          </div>
        ),
      }),
      columnHelper.accessor('last_login_at', {
        header: 'Último acesso',
        cell: (info) => {
          const value = info.getValue()
          return (
            <span className="text-sm text-muted">
              {value ? new Date(value).toLocaleString('pt-BR') : 'nunca acessou'}
            </span>
          )
        },
      }),
      columnHelper.display({
        id: 'actions',
        header: '',
        cell: (info) =>
          hasPermission('users:write') ? (
            <Button variant="ghost" size="sm" onClick={() => setEditing(info.row.original)}>
              <Settings2 /> Gerenciar
            </Button>
          ) : null,
      }),
    ],
    [hasPermission],
  )

  const table = useReactTable({
    data: query.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
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
            placeholder="Buscar por nome ou e-mail"
            value={search}
            onChange={(event) => {
              setPage(1)
              setSearch(event.target.value)
            }}
            aria-label="Buscar usuários"
          />
        </div>
        <select
          className="h-10 rounded-md border border-border bg-surface px-3 text-sm"
          value={status}
          onChange={(event) => {
            setPage(1)
            setStatus(event.target.value)
          }}
          aria-label="Filtrar por status"
        >
          <option value="">Todos os status</option>
          <option value="ACTIVE">Ativos</option>
          <option value="PENDING">Pendentes</option>
          <option value="SUSPENDED">Suspensos</option>
        </select>
      </div>

      {query.isLoading && <SkeletonList rows={4} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.data && query.data.items.length === 0 && (
        <EmptyState
          icon={Users}
          title="Nenhum usuário encontrado"
          description="Ajuste a busca ou o filtro de status para ver outros resultados."
        />
      )}

      {query.data && query.data.items.length > 0 && (
        <>
          <TableWrapper>
            <Table>
              <thead>
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <Th key={header.id}>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </Th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <Tr key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <Td key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </Td>
                    ))}
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrapper>

          <div className="flex items-center justify-between text-sm text-muted">
            <span>
              {query.data.total} usuário(s) · página {query.data.page} de {query.data.pages}
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

      <UserEditDialog user={editing} onClose={() => setEditing(null)} />
    </div>
  )
}

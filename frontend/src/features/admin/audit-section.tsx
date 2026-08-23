import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ScrollText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableWrapper, Td, Th, Tr } from '@/components/ui/table'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { adminApi } from '@/lib/api/admin'
import { queryKeys } from '@/lib/query-client'

const actionLabels: Record<string, string> = {
  'user.registered': 'Cadastro',
  'user.login': 'Login',
  'user.login_failed': 'Login recusado',
  'user.logout': 'Logout',
  'user.logout_all': 'Logout global',
  'user.email_verified': 'E-mail confirmado',
  'user.password_changed': 'Senha alterada',
  'user.password_reset': 'Senha redefinida',
  'user.profile_updated': 'Perfil atualizado',
  'user.data_exported': 'Dados exportados',
  'user.account_deleted': 'Conta excluída',
  'session.revoked': 'Sessão encerrada',
  'session.reuse_detected': 'Reuso de token bloqueado',
  'admin.user_updated': 'Usuário alterado',
  'admin.roles_assigned': 'Papéis alterados',
  'permission.denied': 'Acesso negado',
}

export function AuditSection() {
  const [page, setPage] = useState(1)
  const [action, setAction] = useState('')

  const params = { page, page_size: 25, action }
  const query = useQuery({
    queryKey: queryKeys.adminAudit(params),
    queryFn: () => adminApi.auditLogs(params),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="space-y-4">
      <select
        className="h-10 rounded-md border border-border bg-surface px-3 text-sm"
        value={action}
        onChange={(event) => {
          setPage(1)
          setAction(event.target.value)
        }}
        aria-label="Filtrar por ação"
      >
        <option value="">Todas as ações</option>
        {Object.entries(actionLabels).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>

      {query.isLoading && <SkeletonList rows={5} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.data && query.data.items.length === 0 && (
        <EmptyState
          icon={ScrollText}
          title="Nenhum registro"
          description="Ainda não há eventos de auditoria para o filtro selecionado."
        />
      )}

      {query.data && query.data.items.length > 0 && (
        <>
          <TableWrapper>
            <Table>
              <thead>
                <tr>
                  <Th>Quando</Th>
                  <Th>Ação</Th>
                  <Th>Responsável</Th>
                  <Th>Recurso</Th>
                  <Th>Resultado</Th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((log) => (
                  <Tr key={log.id}>
                    <Td className="text-sm whitespace-nowrap text-muted">
                      {new Date(log.created_at).toLocaleString('pt-BR')}
                    </Td>
                    <Td className="text-sm font-medium">
                      {actionLabels[log.action] ?? log.action}
                    </Td>
                    <Td className="text-sm text-muted">
                      {log.actor_email ?? '—'}
                      {log.actor_ip && (
                        <span className="block text-xs text-subtle">{log.actor_ip}</span>
                      )}
                    </Td>
                    <Td className="text-xs text-subtle">
                      {log.resource_type ? `${log.resource_type} ${log.resource_id ?? ''}` : '—'}
                    </Td>
                    <Td>
                      <Badge
                        variant={
                          log.status === 'SUCCESS'
                            ? 'success'
                            : log.status === 'FAILURE'
                              ? 'warning'
                              : 'danger'
                        }
                      >
                        {log.status}
                      </Badge>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrapper>

          <div className="flex items-center justify-between text-sm text-muted">
            <span>
              {query.data.total} registro(s) · página {query.data.page} de {query.data.pages}
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
    </div>
  )
}

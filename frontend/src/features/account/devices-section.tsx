import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Laptop, LogOut, Smartphone } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { usersApi } from '@/lib/api/users'
import { queryKeys } from '@/lib/query-client'
import { ApiError } from '@/lib/api/client'

function formatMoment(value: string | null): string {
  if (!value) return 'sem registro'
  return new Date(value).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function isMobile(userAgent: string | null): boolean {
  return /Android|iPhone|iPad|Mobile/i.test(userAgent ?? '')
}

export function DevicesSection() {
  const queryClient = useQueryClient()
  const sessions = useQuery({ queryKey: queryKeys.sessions, queryFn: usersApi.sessions })

  const revoke = useMutation({
    mutationFn: (publicId: string) => usersApi.revokeSession(publicId),
    onSuccess: () => {
      toast.success('Dispositivo desconectado.')
      queryClient.invalidateQueries({ queryKey: queryKeys.sessions })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível desconectar.'),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Dispositivos conectados</CardTitle>
        <CardDescription>
          Sessões ativas na sua conta. Encerre qualquer uma que você não reconheça.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sessions.isLoading && <SkeletonList rows={2} />}
        {sessions.isError && (
          <ErrorState error={sessions.error} onRetry={() => sessions.refetch()} />
        )}
        {sessions.data?.length === 0 && (
          <EmptyState
            icon={Laptop}
            title="Nenhuma sessão ativa"
            description="Quando você entrar em um dispositivo, ele aparecerá aqui."
          />
        )}
        <ul className="divide-y divide-border">
          {sessions.data?.map((session) => {
            const Icon = isMobile(session.user_agent) ? Smartphone : Laptop
            return (
              <li key={session.public_id} className="flex items-center gap-4 py-4">
                <span className="rounded-md bg-surface-muted p-2 text-muted">
                  <Icon className="size-4" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm font-medium">
                    {session.device_label ?? 'Dispositivo desconhecido'}
                    {session.is_current && <Badge variant="success">Esta sessão</Badge>}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {session.ip_address ?? 'IP não registrado'} · último uso em{' '}
                    {formatMoment(session.last_used_at)}
                  </p>
                </div>
                {!session.is_current && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => revoke.mutate(session.public_id)}
                    loading={revoke.isPending && revoke.variables === session.public_id}
                  >
                    <LogOut /> Encerrar
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

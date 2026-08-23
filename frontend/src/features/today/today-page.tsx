import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  CalendarClock,
  CheckCircle2,
  Circle,
  FileText,
  Lock,
  MonitorSmartphone,
  Target,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { usersApi } from '@/lib/api/users'
import { queryKeys } from '@/lib/query-client'
import { useAuth } from '@/providers/auth-provider'
import { firstName, greeting } from '@/lib/utils'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Cada passo reflete um estado real da conta — nada aqui é ilustrativo. */
function SetupStep({
  done,
  locked,
  title,
  description,
  phase,
  action,
}: {
  done?: boolean
  locked?: boolean
  title: string
  description: string
  phase?: string
  action?: ReactNode
}) {
  return (
    <li className="flex items-start gap-3 border-b border-border/60 py-3 last:border-0">
      {done ? (
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" aria-hidden />
      ) : locked ? (
        <Lock className="mt-0.5 size-5 shrink-0 text-subtle" aria-hidden />
      ) : (
        <Circle className="mt-0.5 size-5 shrink-0 text-muted" aria-hidden />
      )}
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-sm font-medium">
          {title}
          {phase && <Badge variant="outline">{phase}</Badge>}
        </p>
        <p className="text-sm text-muted">{description}</p>
      </div>
      {action}
    </li>
  )
}

export function TodayPage() {
  const { user } = useAuth()
  const sessions = useQuery({ queryKey: queryKeys.sessions, queryFn: usersApi.sessions })

  if (!user) return null

  const memberSince = new Date(user.created_at).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  })

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-sm text-muted">{greeting()},</p>
        <h1 className="text-3xl font-semibold tracking-tight">{firstName(user.full_name)}.</h1>
      </header>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Sua missão de hoje</CardTitle>
              <CardDescription>
                A missão diária é montada a partir do seu edital, da banca e do seu desempenho.
              </CardDescription>
            </div>
            <Badge variant="primary">Fundação concluída</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-md border border-dashed border-border p-5 text-sm text-muted">
            <p className="text-foreground">
              Ainda não há edital vinculado à sua conta, então não existe missão para exibir.
            </p>
            <p className="mt-1">
              A plataforma não sugere estudo sem base. O catálogo de concursos já está no ar;
              quando o analisador de edital (Fase 3) e o planejador adaptativo (Fase 4)
              entrarem, esta área passa a mostrar o que estudar hoje, por quanto tempo e por
              quê.
            </p>
          </div>

          <ul>
            <SetupStep done title="Conta criada" description={`Membro desde ${memberSince}.`} />
            <SetupStep
              done={Boolean(user.email_verified_at)}
              title="E-mail confirmado"
              description={
                user.email_verified_at
                  ? `Confirmado em ${formatDate(user.email_verified_at)}.`
                  : 'Confirme seu e-mail para liberar todos os recursos.'
              }
            />
            <SetupStep
              title="Escolher seu concurso"
              description="O catálogo já traz certames, cargos, disciplinas e editais oficiais."
              action={
                <Button asChild variant="outline" size="sm">
                  <Link to="/concursos">Ver concursos</Link>
                </Button>
              }
            />
            <SetupStep
              locked
              phase="Fase 3"
              title="Enviar meu edital"
              description="Upload do PDF, extração com evidência por página e Raio-X do concurso."
            />
            <SetupStep
              locked
              phase="Fase 4"
              title="Gerar plano de estudo"
              description="Distribuição de teoria, questões, revisões e simulados na sua agenda."
            />
          </ul>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted">
              <CalendarClock className="size-4" aria-hidden /> Último acesso
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">{formatDate(user.last_login_at)}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted">
              <MonitorSmartphone className="size-4" aria-hidden /> Dispositivos conectados
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between gap-2">
            {sessions.isLoading ? (
              <Skeleton className="h-7 w-10" />
            ) : (
              <p className="text-lg font-semibold">{sessions.data?.length ?? '—'}</p>
            )}
            <Button asChild variant="ghost" size="sm">
              <Link to="/conta">Gerenciar</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted">
              <Target className="size-4" aria-hidden /> Perfil de acesso
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {user.roles.map((role) => (
              <Badge key={role.slug} variant="primary">
                {role.name}
              </Badge>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="size-4 text-muted" aria-hidden /> O que vem a seguir
          </CardTitle>
          <CardDescription>
            Roteiro público das próximas entregas — cada fase mantém a aplicação executável.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="grid gap-3 sm:grid-cols-2">
            {[
              ['Fase 3', 'Analisador de edital com IA, RAG e Raio-X'],
              ['Fase 4', 'Planejador adaptativo, agenda e sessões de estudo'],
              ['Fase 5', 'Banco de questões e simulados'],
              ['Fase 6', 'Priority Score, DNA da banca e caderno de erros'],
            ].map(([phase, description]) => (
              <li key={phase} className="rounded-md bg-surface-muted p-3">
                <p className="text-xs font-semibold tracking-wide text-primary uppercase">
                  {phase}
                </p>
                <p className="text-sm text-muted">{description}</p>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  )
}

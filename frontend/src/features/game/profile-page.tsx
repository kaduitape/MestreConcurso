import { useQuery } from '@tanstack/react-query'
import { Award, Info } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import { useAuth } from '@/providers/auth-provider'
import { AchievementCard } from './components/achievement-card'
import { RankHistoryChart } from './components/rank-history-chart'
import { RankPanel } from './components/rank-badge'
import { StreakCounter } from './components/streak-counter'
import { CountUp, XPBar } from './components/xp-bar'
import { EVENT_LABEL } from './helpers'

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <p className="text-sm text-muted">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-subtle">{hint}</p>}
    </div>
  )
}

export function GameProfilePage() {
  const { user } = useAuth()

  const profile = useQuery({
    queryKey: queryKeys.gameProfile,
    queryFn: () => gameApi.profile(),
  })
  const achievements = useQuery({
    queryKey: queryKeys.gameAchievements,
    queryFn: () => gameApi.achievements(),
  })
  const history = useQuery({
    queryKey: queryKeys.gameXpHistory({ page: 1 }),
    queryFn: () => gameApi.xpHistory({ page: 1, page_size: 30 }),
  })
  const rankHistory = useQuery({
    queryKey: queryKeys.gameRankHistory(90),
    queryFn: () => gameApi.rankHistory(90),
  })

  if (profile.isLoading) return <SkeletonList rows={4} />
  if (profile.isError)
    return <ErrorState error={profile.error} onRetry={() => profile.refetch()} />

  const data = profile.data!
  const metrics = data.metrics

  return (
    <div className="space-y-6">
      <PageHeader
        title={user?.full_name ?? 'Meu progresso'}
        description="Onde você está, medido pelo que você fez."
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardContent className="space-y-4 pt-6">
            <XPBar level={data.level} />
            <div className="grid grid-cols-2 gap-4 border-t border-border pt-4 sm:grid-cols-4">
              <Stat
                label="Horas de foco"
                value={`${(metrics.focus_hours ?? 0).toString().replace('.', ',')}h`}
              />
              <Stat
                label="Questões"
                value={String(Math.round(metrics.questions_answered ?? 0))}
              />
              <Stat
                label="Acerto"
                value={
                  (metrics.questions_answered ?? 0) > 0
                    ? `${((metrics.accuracy ?? 0) * 100).toFixed(0)}%`
                    : '—'
                }
                hint={(metrics.questions_answered ?? 0) > 0 ? undefined : 'sem respostas ainda'}
              />
              <Stat
                label="Revisões"
                value={String(Math.round(metrics.flashcard_reviews ?? 0))}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Sequência</CardTitle>
          </CardHeader>
          <CardContent>
            <StreakCounter streak={data.streak} />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Rank</CardTitle>
            <CardDescription>Mede desempenho real. XP não entra nesta conta.</CardDescription>
          </CardHeader>
          <CardContent>
            <RankPanel rank={data.rank} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Evolução do rank</CardTitle>
            <CardDescription>
              O rank pode cair — um número que só sobe não mediria nada.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {rankHistory.isLoading && <SkeletonList rows={2} />}
            {rankHistory.data && <RankHistoryChart history={rankHistory.data} />}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Mestre Score</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="flex items-start gap-2 text-sm text-muted">
              <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
              {data.master_score_note}
            </p>
            <p className="text-xs text-subtle">
              Enquanto ele não existe, o rank acima é a medida de desempenho da plataforma.
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="conquistas">
        <TabsList>
          <TabsTrigger value="conquistas">
            Conquistas
            {achievements.data && ` (${achievements.data.unlocked_count})`}
          </TabsTrigger>
          <TabsTrigger value="extrato">Extrato de XP</TabsTrigger>
        </TabsList>

        <TabsContent value="conquistas" className="space-y-4">
          {achievements.isLoading && <SkeletonList rows={3} />}
          {achievements.data && (
            <>
              <p className="text-sm text-muted">
                {achievements.data.unlocked_count} de{' '}
                {achievements.data.total_visible + achievements.data.secret_count} conquistas.{' '}
                {achievements.data.secret_count > 0 && (
                  <>
                    Há {achievements.data.secret_count} secreta(s) — elas aparecem quando
                    acontecem.
                  </>
                )}
              </p>
              <ul className="grid gap-3 md:grid-cols-2">
                {achievements.data.items.map((item) => (
                  <AchievementCard key={item.slug} achievement={item} />
                ))}
              </ul>
              {achievements.data.items.length === 0 && (
                <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
                  <Award className="mx-auto mb-2 size-5" aria-hidden />
                  Nenhuma conquista ainda. Elas são avaliadas sobre o que você realmente fez.
                </p>
              )}
            </>
          )}
        </TabsContent>

        <TabsContent value="extrato" className="space-y-3">
          <p className="text-sm text-muted">
            Todo ponto tem origem declarada. O saldo do perfil é a soma exata deste extrato.
          </p>
          {history.isLoading && <SkeletonList rows={4} />}
          {history.data?.items.length === 0 && (
            <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
              Nenhum XP registrado ainda.
            </p>
          )}
          <ul className="space-y-2">
            {history.data?.items.map((item) => (
              <li
                key={item.public_id}
                className="flex flex-wrap items-start gap-3 rounded-md border border-border p-3 text-sm"
              >
                <Badge variant={item.capped ? 'warning' : 'primary'}>
                  +<CountUp value={item.amount} duration={300} /> XP
                </Badge>
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">
                    {EVENT_LABEL[item.event_kind] ?? item.event_kind}
                  </span>
                  <span className="block text-xs text-muted">{item.reason}</span>
                  {item.cap_reason && (
                    <span className="mt-1 block text-xs text-warning">{item.cap_reason}</span>
                  )}
                </span>
                <span className="text-xs text-subtle">
                  {new Date(item.created_at).toLocaleString('pt-BR')}
                </span>
              </li>
            ))}
          </ul>
        </TabsContent>
      </Tabs>
    </div>
  )
}

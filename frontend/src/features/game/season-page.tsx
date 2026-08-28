import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Trophy, Users } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import { LeagueTable } from './components/league-table'
import { SeasonProgress } from './components/season-progress'

export function SeasonPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')

  const season = useQuery({ queryKey: queryKeys.gameSeason, queryFn: () => gameApi.season() })
  const league = useQuery({ queryKey: queryKeys.gameLeague, queryFn: () => gameApi.league() })
  const preferences = useQuery({
    queryKey: queryKeys.gameLeaguePreferences,
    queryFn: () => gameApi.leaguePreferences(),
  })
  const history = useQuery({
    queryKey: queryKeys.gameSeasonHistory,
    queryFn: () => gameApi.seasonHistory(),
  })

  const update = useMutation({
    mutationFn: (input: { opt_out?: boolean; display_name?: string }) =>
      gameApi.updateLeaguePreferences(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['game'] })
      toast.success('Preferência salva.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  if (season.isLoading) return <SkeletonList rows={3} />
  if (season.isError)
    return <ErrorState error={season.error} onRetry={() => season.refetch()} />

  const data = season.data!
  const prefs = preferences.data

  return (
    <div className="space-y-6">
      <PageHeader
        title={data.name ?? 'Temporada'}
        description={data.description ?? 'Um período fechado, com placar próprio.'}
      />

      {data.name === null ? (
        <EmptyState
          icon={Trophy}
          title="Nenhuma temporada aberta"
          description={data.empty_reason ?? 'As temporadas são períodos definidos pela equipe.'}
        />
      ) : (
        <Card>
          <CardContent className="pt-6">
            <SeasonProgress season={data} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Minha liga</CardTitle>
          <CardDescription>
            A comparação é entre candidatos ao mesmo cargo — e é opcional.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {league.isLoading && <SkeletonList rows={3} />}
          {league.data && <LeagueTable league={league.data} />}

          {prefs && (
            <div className="space-y-3 border-t border-border pt-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">
                    {prefs.opt_out ? 'Comparação desligada' : 'Comparação ligada'}
                  </p>
                  <p className="text-xs text-muted">
                    Desligar remove você da tabela dos outros — e nada do seu estudo depende
                    disso.
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => update.mutate({ opt_out: !prefs.opt_out })}
                  disabled={update.isPending}
                >
                  {prefs.opt_out ? 'Voltar a participar' : 'Sair da comparação'}
                </Button>
              </div>

              {!prefs.opt_out && (
                <div className="space-y-2">
                  <p className="text-xs text-muted">
                    Você aparece como “Candidato #{league.data?.your_position ?? '—'}”. Se
                    quiser, escolha um nome para exibir.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Input
                      value={name}
                      maxLength={40}
                      placeholder={prefs.display_name ?? 'Como você quer aparecer'}
                      onChange={(event) => setName(event.target.value)}
                      className="max-w-xs"
                      aria-label="Nome de exibição na liga"
                    />
                    <Button
                      variant="outline"
                      onClick={() => update.mutate({ display_name: name })}
                      disabled={update.isPending}
                    >
                      Salvar
                    </Button>
                    {prefs.display_name && (
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setName('')
                          update.mutate({ display_name: '' })
                        }}
                        disabled={update.isPending}
                      >
                        Voltar ao anonimato
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {history.data && history.data.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Temporadas anteriores</CardTitle>
            <CardDescription>Posições congeladas no fechamento.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {history.data.map((item) => (
                <li
                  key={`${item.season_name}-${item.closed_at}`}
                  className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-3 last:border-b-0 last:pb-0"
                >
                  <span className="font-medium">{item.season_name}</span>
                  <span className="flex items-center gap-3 text-xs text-muted">
                    <span className="tabular-nums">{item.seasonal_xp} XP</span>
                    {item.position !== null && (
                      <span className="inline-flex items-center gap-1">
                        <Users className="size-3" aria-hidden />
                        {item.position}º de {item.participants}
                      </span>
                    )}
                    {item.rewards.map((reward) => (
                      <span key={reward.slug}>{reward.label}</span>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

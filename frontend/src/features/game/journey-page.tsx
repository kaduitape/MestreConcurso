import { useQuery } from '@tanstack/react-query'
import { Map, Route } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import { JourneyMap } from './components/journey-map'
import { StudyTerritory } from './components/study-territory'

export function JourneyPage() {
  const journey = useQuery({
    queryKey: queryKeys.gameJourney,
    queryFn: () => gameApi.journey(),
  })
  const territory = useQuery({
    queryKey: queryKeys.gameTerritory,
    queryFn: () => gameApi.territory(),
  })

  if (journey.isLoading) return <SkeletonList rows={4} />
  if (journey.isError)
    return <ErrorState error={journey.error} onRetry={() => journey.refetch()} />

  const data = journey.data!
  const map = territory.data

  return (
    <div className="space-y-6">
      <PageHeader
        title="Jornada da aprovação"
        description={
          data.days_until_exam !== null
            ? `Faltam ${data.days_until_exam} dias para a prova do seu plano.`
            : 'Onde você está, medido pelo que você fez.'
        }
      />

      {data.milestones.length === 0 ? (
        <EmptyState
          icon={Route}
          title="A jornada começa no plano"
          description={data.empty_reason ?? 'Monte o seu plano de estudo.'}
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Marcos</CardTitle>
            <CardDescription>
              {data.completed} de {data.total} cumpridos. Cada marco tem critério verificável.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <JourneyMap journey={data} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Mapa do edital</CardTitle>
          <CardDescription>
            {map && map.territories.length > 0
              ? `${map.mastered} disciplina(s) com domínio consolidado · ${map.needs_review} pedindo revisão. A lista começa pelo território mais frágil.`
              : 'Cada disciplina do plano como um território, com o estado real dela.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {territory.isLoading && <SkeletonList rows={3} />}
          {territory.isError && (
            <ErrorState error={territory.error} onRetry={() => territory.refetch()} />
          )}
          {map && map.territories.length === 0 && (
            <EmptyState
              icon={Map}
              title="Sem territórios ainda"
              description={map.empty_reason ?? 'Monte o seu plano de estudo.'}
            />
          )}
          {map && map.territories.length > 0 && (
            <div className="grid gap-3 md:grid-cols-2">
              {map.territories.map((item) => (
                <StudyTerritory key={item.subject_key} territory={item} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

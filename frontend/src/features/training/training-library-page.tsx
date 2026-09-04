import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CirclePlay, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/feedback/empty-state'
import { SkeletonList } from '@/components/ui/skeleton'
import { trainingApi } from '@/lib/api/training'
import { queryKeys } from '@/lib/query-client'

export function TrainingLibraryPage() {
  const trainings = useQuery({
    queryKey: queryKeys.training({ page: 1, page_size: 30 }),
    queryFn: () => trainingApi.published({ page: 1, page_size: 30 }),
  })
  return (
    <div className="space-y-6">
      <div>
        <p className="game-label text-game-purple-light">Aprendizado imersivo</p>
        <h1 className="mt-1 text-2xl font-extrabold text-white">Dia de treinamento</h1>
        <p className="mt-2 text-sm text-slate-400">
          Missões guiadas por personagens, com conceitos destacados e desafios de revisão.
        </p>
      </div>
      {trainings.isLoading && <SkeletonList rows={4} />}
      {trainings.data?.items.length === 0 && (
        <EmptyState
          icon={Sparkles}
          title="Nenhum treinamento publicado"
          description="Assim que o estúdio publicar uma missão, ela aparecerá aqui."
        />
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {trainings.data?.items.map((training) => (
          <Card
            key={training.public_id}
            className="group border-game-purple/20 transition hover:-translate-y-0.5 hover:border-game-purple/45"
          >
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <Badge variant="success">Missão</Badge>
                <span className="text-xs text-muted">
                  {training.target_duration_minutes} min
                </span>
              </div>
              <CardTitle className="mt-3">{training.title}</CardTitle>
              <CardDescription>
                {training.subject} · {training.topic}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted">Conduzido por {training.character_name}</p>
              <Link
                to={`/dia-de-treinamento/${training.public_id}`}
                className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline"
              >
                <CirclePlay className="size-4" /> Iniciar missão
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

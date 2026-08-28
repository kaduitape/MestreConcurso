import { useQuery } from '@tanstack/react-query'
import { Swords } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import { BattleBar, BattleEvolution, SubjectScoreRow } from './components/battle-bar'

export function BoardBattlePage() {
  const battle = useQuery({
    queryKey: queryKeys.gameBoardBattle,
    queryFn: () => gameApi.boardBattle(),
  })

  if (battle.isLoading) return <SkeletonList rows={3} />
  if (battle.isError)
    return <ErrorState error={battle.error} onRetry={() => battle.refetch()} />

  const data = battle.data!

  if (!data.is_sufficient) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Você vs Banca"
          description="O placar é a sua taxa de acerto real contra a banca do concurso-alvo."
        />
        <EmptyState
          icon={Swords}
          title={
            data.board_name ? `Ainda não há placar contra a ${data.board_name}` : 'Sem placar'
          }
          description={data.empty_reason ?? 'Responda mais questões desta banca.'}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Você vs ${data.board_name}`}
        description={`Baseado em ${data.answers} respostas suas a questões desta banca.`}
      />

      <Card>
        <CardContent className="space-y-4 pt-6">
          <BattleBar you={data.you} board={data.board} boardName={data.board_name} />
          <p className="text-sm text-muted">
            Você acertou {data.correct} de {data.answers} questões. Os {data.board} pontos da
            banca são exatamente as questões que você errou — não há adversário simulado aqui.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Por disciplina</CardTitle>
          <CardDescription>
            Disciplina com menos de 30 respostas não recebe placar: amostra pequena não decide
            nada.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul>
            {data.subjects.map((subject) => (
              <SubjectScoreRow
                key={`${subject.subject_id ?? 'sem'}-${subject.subject_name}`}
                subject={subject}
                boardName={data.board_name}
              />
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Evolução</CardTitle>
          <CardDescription>Seu acerto nesta banca, semana a semana.</CardDescription>
        </CardHeader>
        <CardContent>
          <BattleEvolution weeks={data.evolution} />
        </CardContent>
      </Card>
    </div>
  )
}

/**
 * O concurso principal e a contagem regressiva.
 *
 * A regra é a mesma da barra de FOCO da batalha: **sem dado real não há
 * número**. Sem concurso escolhido, não há contagem. Sem data de prova no
 * edital, também não — e aí o cartão escreve o motivo, em vez de mostrar um
 * traço que ninguém sabe interpretar.
 */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CalendarClock, Target } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { studyFocusApi } from '@/lib/api/catalog-link'
import { queryKeys } from '@/lib/query-client'

/** Formata a data da prova sem deslocar o dia pelo fuso. */
function formatExamDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  })
}

export function StudyFocusCard() {
  const focus = useQuery({
    queryKey: queryKeys.studyFocus,
    queryFn: () => studyFocusApi.get(),
    retry: false,
  })

  if (focus.isLoading) return <Skeleton className="h-28" />
  if (!focus.data) return null

  const { competition_name, organization_name, exam_date, days_remaining, unavailable_reason } =
    focus.data

  if (!competition_name) {
    return (
      <Card className="border-game-gold/25">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-5">
          <div className="flex items-center gap-3">
            <Target className="size-5 text-game-gold" aria-hidden />
            <div>
              <p className="text-sm font-semibold text-white">Escolha seu concurso</p>
              <p className="text-xs text-muted">{unavailable_reason}</p>
            </div>
          </div>
          <Link
            to="/concursos"
            className="text-sm font-semibold text-primary hover:underline"
          >
            Ver concursos
          </Link>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-game-gold/25">
      <CardContent className="flex flex-wrap items-center justify-between gap-4 py-5">
        <div className="flex min-w-0 items-center gap-3">
          <Target className="size-5 shrink-0 text-game-gold" aria-hidden />
          <div className="min-w-0">
            <p className="game-label text-game-gold">Meu concurso</p>
            <p className="truncate text-sm font-bold text-white">{competition_name}</p>
            {organization_name && (
              <p className="truncate text-xs text-muted">{organization_name}</p>
            )}
          </div>
        </div>

        {days_remaining === null ? (
          // Sem data no edital não há contagem, e o motivo fica escrito.
          <p className="flex items-center gap-2 text-xs text-muted">
            <CalendarClock className="size-4" aria-hidden />
            {unavailable_reason}
          </p>
        ) : (
          <div className="text-right">
            <p className="text-2xl font-extrabold text-white tabular-nums">{days_remaining}</p>
            <p className="game-label text-[0.6rem] text-muted">
              {days_remaining === 1 ? 'dia para a prova' : 'dias para a prova'}
            </p>
            {exam_date && (
              <p className="mt-0.5 text-[0.68rem] text-slate-500">{formatExamDate(exam_date)}</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

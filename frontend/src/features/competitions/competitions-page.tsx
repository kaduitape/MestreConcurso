import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Briefcase, CalendarDays, MapPin, Search, Users } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { catalogApi } from '@/lib/api/catalog'
import { queryKeys } from '@/lib/query-client'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { STATUS_LABEL, daysUntil, formatCurrency, formatDate } from '../admin/catalog/helpers'

export function CompetitionsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const debounced = useDebouncedValue(search, 350)

  const params = { page, page_size: 12, search: debounced }
  const query = useQuery({
    queryKey: queryKeys.competitions(params),
    queryFn: () => catalogApi.competitions(params),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Concursos"
        description="Certames cadastrados na plataforma, com cargos, disciplinas e editais."
      />

      <div className="relative max-w-md">
        <Search
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle"
          aria-hidden
        />
        <Input
          className="pl-9"
          placeholder="Buscar por nome do concurso"
          value={search}
          onChange={(event) => {
            setPage(1)
            setSearch(event.target.value)
          }}
          aria-label="Buscar concursos"
        />
      </div>

      {query.isLoading && <SkeletonList rows={4} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.data?.items.length === 0 && (
        <EmptyState
          icon={Briefcase}
          title="Nenhum concurso encontrado"
          description={
            search
              ? 'Nenhum resultado para esta busca. Tente outro termo.'
              : 'Ainda não há concursos publicados. Assim que a equipe cadastrar um certame, ele aparece aqui.'
          }
        />
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {query.data?.items.map((competition) => {
          const remaining = daysUntil(competition.exam_date)
          return (
            <Card key={competition.public_id} className="flex flex-col">
              <CardContent className="flex flex-1 flex-col gap-3 p-5">
                <div className="flex items-start justify-between gap-2">
                  <Badge variant="outline">{STATUS_LABEL[competition.status]}</Badge>
                  {remaining !== null && remaining >= 0 && (
                    <Badge variant="primary">{remaining} dias para a prova</Badge>
                  )}
                </div>

                <div>
                  <h2 className="font-semibold tracking-tight">{competition.name}</h2>
                  <p className="text-sm text-muted">
                    {competition.organization.short_name}
                    {competition.exam_board && ` · ${competition.exam_board.short_name}`}
                  </p>
                </div>

                <dl className="grid grid-cols-2 gap-2 text-sm">
                  <div className="flex items-center gap-1.5 text-muted">
                    <CalendarDays className="size-4" aria-hidden />
                    <span>{formatDate(competition.exam_date)}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-muted">
                    <Users className="size-4" aria-hidden />
                    <span>
                      {competition.vacancies_total
                        ? `${competition.vacancies_total.toLocaleString('pt-BR')} vagas`
                        : 'vagas não informadas'}
                    </span>
                  </div>
                  <div className="col-span-2 flex items-center gap-1.5 text-muted">
                    <MapPin className="size-4" aria-hidden />
                    <span>
                      {competition.organization.uf ?? 'Nacional'} ·{' '}
                      {formatCurrency(competition.salary_max_cents)}
                    </span>
                  </div>
                </dl>

                <Button asChild variant="outline" className="mt-auto">
                  <Link to={`/concursos/${competition.public_id}`}>Ver detalhes</Link>
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {query.data && query.data.pages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted">
          <span>
            {query.data.total} concurso(s) · página {query.data.page} de {query.data.pages}
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
      )}
    </div>
  )
}

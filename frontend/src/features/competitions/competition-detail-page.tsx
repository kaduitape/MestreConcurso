import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Brain,
  CalendarDays,
  Download,
  FileText,
  GraduationCap,
  Users,
} from 'lucide-react'
import { Badge, ProvenanceBadge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton, SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { catalogApi } from '@/lib/api/catalog'
import { queryKeys } from '@/lib/query-client'
import {
  EDUCATION_LABEL,
  STATUS_LABEL,
  daysUntil,
  formatCurrency,
  formatDate,
} from '../admin/catalog/helpers'

const SOURCE_TONE = {
  COMPUTED: 'HISTORICO',
  AI: 'IA',
  EDITORIAL: 'HISTORICO',
  OFFICIAL: 'OFICIAL',
} as const

export function CompetitionDetailPage() {
  const { publicId = '' } = useParams()

  const competition = useQuery({
    queryKey: queryKeys.competition(publicId),
    queryFn: () => catalogApi.competition(publicId),
    enabled: Boolean(publicId),
  })

  const notices = useQuery({
    queryKey: queryKeys.competitionNotices(publicId),
    queryFn: () => catalogApi.competitionNotices(publicId),
    enabled: Boolean(publicId),
  })

  const boardId = competition.data?.exam_board?.public_id
  const knowledge = useQuery({
    queryKey: queryKeys.boardKnowledge(boardId ?? ''),
    queryFn: () => catalogApi.boardKnowledge(boardId!),
    enabled: Boolean(boardId),
  })

  if (competition.isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-72" />
        <SkeletonList rows={3} />
      </div>
    )
  }

  if (competition.isError) {
    return <ErrorState error={competition.error} onRetry={() => competition.refetch()} />
  }

  const data = competition.data
  if (!data) return null
  const remaining = daysUntil(data.exam_date)

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/concursos">
          <ArrowLeft /> Concursos
        </Link>
      </Button>

      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{STATUS_LABEL[data.status]}</Badge>
          {data.exam_board && <Badge variant="primary">{data.exam_board.short_name}</Badge>}
          {remaining !== null && remaining >= 0 && (
            <Badge variant="success">{remaining} dias para a prova</Badge>
          )}
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">{data.name}</h1>
        <p className="text-muted">
          {data.organization.name}
          {data.organization.uf && ` · ${data.organization.uf}`}
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: 'Data da prova',
            value: formatDate(data.exam_date),
            icon: CalendarDays,
          },
          {
            label: 'Vagas',
            value: data.vacancies_total?.toLocaleString('pt-BR') ?? '—',
            icon: Users,
          },
          {
            label: 'Maior salário',
            value: formatCurrency(data.salary_max_cents),
            icon: GraduationCap,
          },
          {
            label: 'Inscrições',
            value:
              data.registration_start || data.registration_end
                ? `${formatDate(data.registration_start)} – ${formatDate(data.registration_end)}`
                : '—',
            icon: CalendarDays,
          },
        ].map((item) => (
          <Card key={item.label}>
            <CardContent className="p-4">
              <p className="flex items-center gap-1.5 text-xs tracking-wide text-subtle uppercase">
                <item.icon className="size-3.5" aria-hidden /> {item.label}
              </p>
              <p className="mt-1 text-lg font-semibold">{item.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Cargos e disciplinas</CardTitle>
          <CardDescription>
            Os pesos vêm do cadastro do concurso. Campos não informados aparecem como traço — a
            plataforma não preenche lacuna com estimativa.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {data.positions.length === 0 && (
            <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
              Os cargos deste concurso ainda não foram cadastrados.
            </p>
          )}

          {data.positions.map((position) => (
            <div key={position.public_id} className="rounded-md border border-border p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="font-medium">{position.name}</h3>
                <p className="text-sm text-muted">
                  {position.education_level
                    ? EDUCATION_LABEL[position.education_level]
                    : 'escolaridade não informada'}
                  {position.vacancies ? ` · ${position.vacancies} vagas` : ''}
                  {position.salary_cents ? ` · ${formatCurrency(position.salary_cents)}` : ''}
                  {position.questions_count ? ` · ${position.questions_count} questões` : ''}
                </p>
              </div>

              {position.subjects.length > 0 ? (
                <ul className="mt-3 space-y-2">
                  {position.subjects.map((item) => (
                    <li
                      key={item.subject.public_id}
                      className="flex flex-wrap items-center gap-2 text-sm"
                    >
                      <span
                        className="size-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: `var(--${item.subject.color_token})` }}
                        aria-hidden
                      />
                      <span className="min-w-0 flex-1 truncate">{item.subject.name}</span>
                      <Badge variant="outline">peso {item.weight}</Badge>
                      {item.questions_count && (
                        <Badge variant="neutral">{item.questions_count} questões</Badge>
                      )}
                      {item.is_eliminatory && <Badge variant="warning">eliminatória</Badge>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-subtle">
                  Disciplinas ainda não vinculadas a este cargo.
                </p>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="size-4 text-muted" aria-hidden /> Editais
            </CardTitle>
            <CardDescription>Documentos oficiais vinculados ao concurso.</CardDescription>
          </CardHeader>
          <CardContent>
            {notices.isLoading && <SkeletonList rows={2} />}
            {notices.data?.length === 0 && (
              <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
                Nenhum edital publicado até agora.
              </p>
            )}
            <ul className="space-y-2">
              {notices.data?.map((notice) => (
                <li key={notice.public_id} className="rounded-md bg-surface-muted p-3">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {notice.title}
                    <ProvenanceBadge kind="OFICIAL" />
                  </p>
                  <p className="text-xs text-muted">
                    {notice.files.length} arquivo(s) ·{' '}
                    {new Date(notice.created_at).toLocaleDateString('pt-BR')}
                  </p>
                  {notice.source_url && (
                    <a
                      href={notice.source_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="mt-1 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <Download className="size-3" aria-hidden /> Fonte oficial
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="size-4 text-muted" aria-hidden /> Sobre a banca
            </CardTitle>
            <CardDescription>
              O que já foi apurado sobre {data.exam_board?.short_name ?? 'a banca'} — guardado
              no banco e reutilizado, com origem e amostra sempre visíveis.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!data.exam_board && (
              <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
                A banca deste concurso ainda não foi definida.
              </p>
            )}

            {data.exam_board && knowledge.isLoading && <SkeletonList rows={2} />}

            {data.exam_board && knowledge.data?.length === 0 && (
              <EmptyState
                icon={Brain}
                title="Nada apurado ainda"
                description="O perfil da banca (DNA) é construído na Fase 6, a partir de provas reais. Nenhum traço é exibido antes disso."
              />
            )}

            <ul className="space-y-3">
              {knowledge.data?.map((entry) => (
                <li key={entry.id} className="rounded-md border border-border p-3">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {entry.title}
                    <ProvenanceBadge kind={SOURCE_TONE[entry.source]} />
                  </p>
                  {entry.content && <p className="mt-1 text-sm text-muted">{entry.content}</p>}
                  <p className="mt-2 text-xs text-subtle">
                    {entry.sample_questions
                      ? `${entry.sample_questions.toLocaleString('pt-BR')} questões`
                      : 'amostra não registrada'}
                    {entry.sample_exams ? ` · ${entry.sample_exams} provas` : ''}
                    {entry.period_start_year && entry.period_end_year
                      ? ` · ${entry.period_start_year}–${entry.period_end_year}`
                      : ''}
                  </p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

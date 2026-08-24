import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ClipboardList, Play, Timer } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { catalogApi } from '@/lib/api/catalog'
import { ApiError } from '@/lib/api/client'
import { simulationsApi } from '@/lib/api/questions'
import { queryKeys } from '@/lib/query-client'
import type { SimulationKind } from '@/lib/api/types'
import { SIMULATION_KINDS, formatPercent } from '@/features/questions/helpers'
import { formatMinutes, formatSeconds } from '@/features/study/helpers'

const OFFERED: SimulationKind[] = ['CUSTOM', 'OFFICIAL', 'ERRORS', 'BOARD', 'FLASH']

export function SimulationsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [kind, setKind] = useState<SimulationKind>('CUSTOM')
  const [count, setCount] = useState(20)
  const [subject, setSubject] = useState('')
  const [board, setBoard] = useState('')
  const [duration, setDuration] = useState('')

  const subjects = useQuery({
    queryKey: ['catalog', 'subjects', 'all'],
    queryFn: () => catalogApi.subjects({ page: 1, page_size: 100 }),
  })
  const boards = useQuery({
    queryKey: ['catalog', 'boards', 'all'],
    queryFn: () => catalogApi.boards({ page: 1, page_size: 100 }),
  })
  const history = useQuery({
    queryKey: queryKeys.simulationHistory,
    queryFn: () => simulationsApi.history(),
  })
  const current = useQuery({
    queryKey: queryKeys.simulationCurrent,
    queryFn: () => simulationsApi.current(),
  })

  const create = useMutation({
    mutationFn: async () => {
      const simulation = await simulationsApi.create({
        kind,
        questions_count: count,
        subject_public_id: kind === 'CUSTOM' && subject ? subject : null,
        board_slug: kind === 'BOARD' && board ? board : null,
        duration_minutes: duration ? Number(duration) : null,
      })
      return simulationsApi.start(simulation.public_id)
    },
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ['simulations'] })
      navigate(`/simulados/${run.attempt.public_id}`)
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível montar o simulado.',
      ),
  })

  const info = SIMULATION_KINDS[kind]

  return (
    <div className="space-y-6">
      <PageHeader
        title="Simulados"
        description="Monte um simulado com regra explícita de composição e receba a correção completa ao final."
      />

      {current.data && (
        <Card className="border-primary">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
            <div>
              <p className="font-medium">
                {current.data.attempt.simulation?.name ?? 'Simulado'} em andamento
              </p>
              <p className="text-sm text-muted">
                {current.data.questions.length} questões ·{' '}
                {current.data.remaining_seconds === null
                  ? 'sem tempo definido'
                  : `${formatSeconds(current.data.remaining_seconds)} restantes`}
              </p>
            </div>
            <Button onClick={() => navigate(`/simulados/${current.data!.attempt.public_id}`)}>
              <Play /> Continuar
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Montar simulado</CardTitle>
            <CardDescription>{info.description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Tipo" htmlFor="sim-kind" hint={info.requires}>
              <Select
                id="sim-kind"
                value={kind}
                onChange={(event) => setKind(event.target.value as SimulationKind)}
              >
                {OFFERED.map((value) => (
                  <option key={value} value={value}>
                    {SIMULATION_KINDS[value].label}
                  </option>
                ))}
              </Select>
            </Field>

            <Field
              label="Questões"
              htmlFor="sim-count"
              hint="Entre 5 e 180. Se o banco tiver menos, o simulado sai com o que existe."
            >
              <Input
                id="sim-count"
                type="number"
                min={5}
                max={180}
                value={count}
                onChange={(event) => setCount(Number(event.target.value))}
              />
            </Field>

            {kind === 'CUSTOM' && (
              <Field label="Disciplina" htmlFor="sim-subject" hint="Opcional">
                <Select
                  id="sim-subject"
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                >
                  <option value="">Todas as disciplinas</option>
                  {subjects.data?.items.map((item) => (
                    <option key={item.public_id} value={item.public_id}>
                      {item.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}

            {kind === 'BOARD' && (
              <Field label="Banca" htmlFor="sim-board">
                <Select
                  id="sim-board"
                  value={board}
                  onChange={(event) => setBoard(event.target.value)}
                >
                  <option value="">Escolha a banca</option>
                  {boards.data?.items.map((item) => (
                    <option key={item.public_id} value={item.slug}>
                      {item.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}

            <Field
              label="Duração (minutos)"
              htmlFor="sim-duration"
              hint="Em branco: 2min30 por questão, padrão das provas objetivas."
            >
              <Input
                id="sim-duration"
                type="number"
                min={5}
                max={480}
                placeholder="automático"
                value={duration}
                onChange={(event) => setDuration(event.target.value)}
              />
            </Field>

            <Button
              className="w-full"
              loading={create.isPending}
              disabled={Boolean(current.data) || (kind === 'BOARD' && !board)}
              onClick={() => create.mutate()}
            >
              <Play /> Montar e iniciar
            </Button>
            {current.data && (
              <p className="text-xs text-muted">
                Encerre o simulado em andamento antes de começar outro.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Simulados encerrados</CardTitle>
            <CardDescription>
              O desempenho de cada execução fica registrado e serve de comparação para a
              próxima.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {history.isLoading && <SkeletonList rows={3} />}
            {history.isError && (
              <ErrorState error={history.error} onRetry={() => history.refetch()} />
            )}
            {history.data?.length === 0 && (
              <EmptyState
                icon={ClipboardList}
                title="Nenhum simulado encerrado"
                description="Assim que você concluir o primeiro, o resultado e a evolução aparecem aqui."
              />
            )}
            <ul className="space-y-2">
              {history.data?.map((attempt) => (
                <li key={attempt.public_id}>
                  <button
                    type="button"
                    onClick={() => navigate(`/simulados/resultado/${attempt.public_id}`)}
                    className="flex w-full items-center gap-3 rounded-md border border-border p-3 text-left transition hover:bg-surface-muted"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">
                        {attempt.simulation?.name ?? 'Simulado'}
                      </span>
                      <span className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-subtle">
                        <span>{new Date(attempt.started_at).toLocaleDateString('pt-BR')}</span>
                        <span className="inline-flex items-center gap-1">
                          <Timer className="size-3" aria-hidden />
                          {formatMinutes(Math.round(attempt.elapsed_seconds / 60))}
                        </span>
                        <span>
                          {attempt.correct_count} certas · {attempt.wrong_count} erradas ·{' '}
                          {attempt.blank_count} em branco
                        </span>
                      </span>
                    </span>
                    <Badge
                      variant={
                        (attempt.analysis.accuracy ?? 0) >= 0.7
                          ? 'success'
                          : (attempt.analysis.accuracy ?? 0) >= 0.5
                            ? 'warning'
                            : 'danger'
                      }
                    >
                      {formatPercent(attempt.analysis.accuracy, 0)}
                    </Badge>
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

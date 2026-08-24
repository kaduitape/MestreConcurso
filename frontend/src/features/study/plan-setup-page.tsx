import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { CalendarClock, Check, Target } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { catalogApi } from '@/lib/api/catalog'
import { studyApi } from '@/lib/api/study'
import { queryKeys } from '@/lib/query-client'
import { WEEKDAYS, formatMinutes } from './helpers'

const PRESETS = [0, 30, 60, 90, 120, 180, 240]

/** Onboarding do plano: escolher o alvo e informar a disponibilidade real. */
export function PlanSetupPage() {
  const navigate = useNavigate()
  const [competitionId, setCompetitionId] = useState('')
  const [positionId, setPositionId] = useState('')
  const [minutes, setMinutes] = useState<Record<number, number>>({
    0: 120,
    1: 120,
    2: 120,
    3: 120,
    4: 120,
    5: 240,
    6: 0,
  })

  const competitions = useQuery({
    queryKey: queryKeys.competitions({ page: 1, page_size: 50 }),
    queryFn: () => catalogApi.competitions({ page: 1, page_size: 50 }),
  })

  const competition = useQuery({
    queryKey: queryKeys.competition(competitionId),
    queryFn: () => catalogApi.competition(competitionId),
    enabled: Boolean(competitionId),
  })

  const create = useMutation({
    mutationFn: () =>
      studyApi.createPlan({
        position_public_id: positionId,
        minutes_by_weekday: minutes,
      }),
    onSuccess: () => {
      toast.success('Plano criado. Sua missão de hoje já está montada.')
      navigate('/hoje')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível criar o plano.'),
  })

  const weeklyMinutes = Object.values(minutes).reduce((total, value) => total + value, 0)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Montar meu plano de estudo"
        description="Escolha o cargo e diga quanto tempo você tem em cada dia. O resto é cálculo."
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="size-4 text-muted" aria-hidden /> 1. Qual é o seu alvo?
          </CardTitle>
          <CardDescription>
            As disciplinas e os pesos vêm do cadastro do concurso.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {competitions.isLoading && <SkeletonList rows={2} />}

          {competitions.data?.items.length === 0 && (
            <EmptyState
              icon={Target}
              title="Nenhum concurso publicado"
              description="Assim que a equipe publicar um concurso, ele aparece aqui para você montar o plano."
            />
          )}

          {competitions.data && competitions.data.items.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Concurso" htmlFor="plan-competition">
                <Select
                  id="plan-competition"
                  value={competitionId}
                  onChange={(event) => {
                    setCompetitionId(event.target.value)
                    setPositionId('')
                  }}
                >
                  <option value="">selecione</option>
                  {competitions.data.items.map((item) => (
                    <option key={item.public_id} value={item.public_id}>
                      {item.name}
                    </option>
                  ))}
                </Select>
              </Field>

              <Field label="Cargo" htmlFor="plan-position">
                <Select
                  id="plan-position"
                  value={positionId}
                  disabled={!competition.data}
                  onChange={(event) => setPositionId(event.target.value)}
                >
                  <option value="">selecione</option>
                  {competition.data?.positions.map((position) => (
                    <option key={position.public_id} value={position.public_id}>
                      {position.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
          )}

          {competition.data && positionId && (
            <div className="rounded-md bg-surface-muted p-3 text-sm">
              <p className="font-medium">
                {competition.data.positions.find((item) => item.public_id === positionId)
                  ?.subjects.length ?? 0}{' '}
                disciplina(s) vinculadas a este cargo
              </p>
              {competition.data.exam_date && (
                <p className="text-muted">
                  Prova em{' '}
                  {new Date(`${competition.data.exam_date}T00:00:00`).toLocaleDateString('pt-BR')}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock className="size-4 text-muted" aria-hidden /> 2. Quanto tempo você
            tem por dia?
          </CardTitle>
          <CardDescription>
            Informe o tempo real, não o ideal. O plano é montado sobre o que existe.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            {WEEKDAYS.map((weekday) => (
              <div key={weekday.value} className="flex flex-wrap items-center gap-3">
                <span className="w-32 text-sm font-medium">{weekday.label}</span>
                <div className="flex flex-wrap gap-1">
                  {PRESETS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setMinutes({ ...minutes, [weekday.value]: preset })}
                      className={
                        minutes[weekday.value] === preset
                          ? 'rounded-md border border-primary bg-primary-soft px-2.5 py-1 text-xs font-medium text-primary'
                          : 'rounded-md border border-border px-2.5 py-1 text-xs text-muted hover:bg-surface-muted'
                      }
                    >
                      {preset === 0 ? 'folga' : formatMinutes(preset)}
                    </button>
                  ))}
                </div>
                <Input
                  className="w-24"
                  type="number"
                  min={0}
                  max={960}
                  step={15}
                  aria-label={`Minutos em ${weekday.label}`}
                  value={minutes[weekday.value] ?? 0}
                  onChange={(event) =>
                    setMinutes({
                      ...minutes,
                      [weekday.value]: Math.max(0, Number(event.target.value) || 0),
                    })
                  }
                />
              </div>
            ))}
          </div>

          <Alert tone={weeklyMinutes > 0 ? 'info' : 'warning'}>
            {weeklyMinutes > 0
              ? `Total semanal: ${formatMinutes(weeklyMinutes)}.`
              : 'Informe pelo menos um dia com tempo disponível.'}
          </Alert>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button
          size="lg"
          loading={create.isPending}
          disabled={!positionId || weeklyMinutes === 0}
          onClick={() => create.mutate()}
        >
          <Check /> Gerar meu plano
        </Button>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarRange, Copy, Share2, Swords } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ApiError } from '@/lib/api/client'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import { DuelBoard } from './components/duel-board'
import { ShareCardPreview } from './components/share-card-preview'
import { WarSchedule } from './components/war-schedule'

const CARD_FIELDS: { key: string; label: string }[] = [
  { key: 'level', label: 'Nível' },
  { key: 'rank', label: 'Rank' },
  { key: 'streak', label: 'Sequência' },
  { key: 'questions', label: 'Questões' },
  { key: 'accuracy', label: 'Acerto' },
  { key: 'retention', label: 'Retenção' },
  { key: 'coverage', label: 'Edital coberto' },
]

function DuelsTab() {
  const queryClient = useQueryClient()
  const [code, setCode] = useState('')
  const [openId, setOpenId] = useState<string | null>(null)

  const duels = useQuery({ queryKey: queryKeys.gameDuels, queryFn: () => gameApi.duels() })
  const open = useQuery({
    queryKey: queryKeys.gameDuel(openId ?? ''),
    queryFn: () => gameApi.duel(openId!),
    enabled: openId !== null,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['game'] })
  const fail = (error: unknown) =>
    toast.error(error instanceof ApiError ? error.message : 'Não foi possível.')

  const create = useMutation({
    mutationFn: () => gameApi.createDuel(),
    onSuccess: (duel) => {
      setOpenId(duel.public_id)
      invalidate()
    },
    onError: fail,
  })

  const accept = useMutation({
    mutationFn: (value: string) => gameApi.acceptDuel(value),
    onSuccess: (duel) => {
      setOpenId(duel.public_id)
      setCode('')
      invalidate()
    },
    onError: fail,
  })

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Novo duelo</CardTitle>
          <CardDescription>
            Os dois lados respondem exatamente as mesmas dez questões. O resultado só sai quando
            ambos terminam.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            Criar desafio
          </Button>
          <span className="text-sm text-subtle">ou</span>
          <Input
            value={code}
            maxLength={12}
            placeholder="Código do convite"
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            className="max-w-[12rem] font-mono tracking-wider"
            aria-label="Código do convite"
          />
          <Button
            variant="outline"
            onClick={() => accept.mutate(code)}
            disabled={accept.isPending || code.length < 4}
          >
            Aceitar
          </Button>
        </CardContent>
      </Card>

      {open.data && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Duelo</CardTitle>
            {open.data.status === 'OPEN' && (
              <CardDescription>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 text-primary"
                  onClick={() => {
                    void navigator.clipboard?.writeText(open.data!.code)
                    toast.success('Código copiado.')
                  }}
                >
                  <Copy className="size-3.5" aria-hidden />
                  copiar código
                </button>
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <DuelBoard duel={open.data} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Meus duelos</CardTitle>
        </CardHeader>
        <CardContent>
          {duels.isLoading && <SkeletonList rows={2} />}
          {duels.data?.length === 0 && (
            <p className="text-sm text-muted">Nenhum duelo ainda.</p>
          )}
          <ul className="space-y-2">
            {duels.data?.map((item) => (
              <li key={item.public_id}>
                <button
                  type="button"
                  onClick={() => setOpenId(item.public_id)}
                  className="flex w-full flex-wrap items-baseline justify-between gap-2 rounded-md border border-border p-3 text-left text-sm hover:border-primary"
                >
                  <span className="font-mono tracking-wider">{item.code}</span>
                  <span className="flex items-center gap-3 text-xs text-muted">
                    {item.headline || item.status}
                    {item.you_won !== null && (
                      <Badge variant={item.you_won ? 'success' : 'neutral'}>
                        {item.you_won ? 'vitória' : 'derrota'}
                      </Badge>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}

function EventsTab() {
  const events = useQuery({ queryKey: queryKeys.gameEvents, queryFn: () => gameApi.events() })

  if (events.isLoading) return <SkeletonList rows={2} />
  if (events.data?.length === 0) {
    return (
      <EmptyState
        icon={CalendarRange}
        title="Nenhum evento aberto"
        description="Eventos são períodos curtos com metas declaradas. Quando houver um, ele aparece aqui."
      />
    )
  }

  return (
    <div className="space-y-4">
      {events.data?.map((event) => (
        <Card key={event.slug}>
          <CardHeader>
            <CardTitle className="text-base">{event.name}</CardTitle>
            <CardDescription>
              {event.description}
              {event.days_left !== null && ` · ${event.days_left} dias restantes`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-3">
              {event.goals.map((goal) => (
                <li key={goal.metric} className="space-y-1">
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span>{goal.label}</span>
                    <span className="font-mono text-xs tabular-nums text-muted">
                      {goal.current} / {goal.target}
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${Math.round(goal.ratio * 100)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>

            {event.reward_label && (
              <div className="rounded-md border border-border p-3">
                <p className="text-sm font-medium">{event.reward_label}</p>
                <p className="text-xs text-muted">{event.reward_utility}</p>
              </div>
            )}

            <p className="text-xs text-subtle">{event.note}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function WarTab() {
  const queryClient = useQueryClient()
  const [days, setDays] = useState('7')
  const [minutes, setMinutes] = useState('120')
  const [questions, setQuestions] = useState('20')

  const war = useQuery({ queryKey: queryKeys.gameWar, queryFn: () => gameApi.warMode() })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['game'] })
  const fail = (error: unknown) =>
    toast.error(error instanceof ApiError ? error.message : 'Não foi possível.')

  const start = useMutation({
    mutationFn: () =>
      gameApi.startWarMode({
        days: Number(days),
        daily_minutes: Number(minutes),
        daily_questions: Number(questions),
      }),
    onSuccess: invalidate,
    onError: fail,
  })
  const abandon = useMutation({
    mutationFn: () => gameApi.abandonWarMode(),
    onSuccess: invalidate,
    onError: fail,
  })

  if (war.isLoading) return <SkeletonList rows={2} />

  const campaign = war.data!

  if (campaign.status === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Declarar um Modo Guerra</CardTitle>
          <CardDescription>{campaign.empty_reason}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="space-y-1 text-sm">
              <span className="text-muted">Dias</span>
              <Input
                value={days}
                onChange={(event) => setDays(event.target.value)}
                inputMode="numeric"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-muted">Minutos por dia</span>
              <Input
                value={minutes}
                onChange={(event) => setMinutes(event.target.value)}
                inputMode="numeric"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span className="text-muted">Questões por dia</span>
              <Input
                value={questions}
                onChange={(event) => setQuestions(event.target.value)}
                inputMode="numeric"
              />
            </label>
          </div>
          <p className="text-xs text-muted">
            A meta é sua. Se ela ficar muito acima do seu histórico, avisamos antes de começar —
            sem impedir.
          </p>
          <Button onClick={() => start.mutate()} disabled={start.isPending}>
            Começar
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          Modo Guerra · {campaign.days} dias
          {campaign.is_over && campaign.succeeded && (
            <Badge variant="success" className="ml-2">
              concluído
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <WarSchedule campaign={campaign} />
        {!campaign.is_over && (
          <Button variant="ghost" onClick={() => abandon.mutate()} disabled={abandon.isPending}>
            Encerrar o período
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

function CardTab() {
  const queryClient = useQueryClient()
  const [include, setInclude] = useState<string[]>(['level', 'rank', 'streak', 'questions'])
  const [name, setName] = useState('')

  const preview = useQuery({
    queryKey: ['game', 'cards', 'preview', include, name],
    queryFn: () => gameApi.previewCard({ include, display_name: name || undefined }),
  })
  const cards = useQuery({ queryKey: queryKeys.gameCards, queryFn: () => gameApi.cards() })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['game'] })
  const publish = useMutation({
    mutationFn: () => gameApi.publishCard({ include, display_name: name || undefined }),
    onSuccess: () => {
      invalidate()
      toast.success('Card publicado. O link só existe porque você pediu.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível publicar.'),
  })
  const revoke = useMutation({
    mutationFn: (publicId: string) => gameApi.revokeCard(publicId),
    onSuccess: () => {
      invalidate()
      toast.success('Link revogado.')
    },
  })

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Card compartilhável</CardTitle>
          <CardDescription>
            Você escolhe o que entra. Nada é publicado por padrão, e o card nunca afirma
            resultado em prova.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {CARD_FIELDS.map((field) => {
              const active = include.includes(field.key)
              return (
                <button
                  key={field.key}
                  type="button"
                  aria-pressed={active}
                  onClick={() =>
                    setInclude((current) =>
                      active
                        ? current.filter((item) => item !== field.key)
                        : [...current, field.key],
                    )
                  }
                  className={
                    active
                      ? 'rounded-full bg-primary px-3 py-1 text-xs text-primary-foreground'
                      : 'rounded-full border border-border px-3 py-1 text-xs text-muted'
                  }
                >
                  {field.label}
                </button>
              )
            })}
          </div>

          <Input
            value={name}
            maxLength={80}
            placeholder="Nome no card (opcional)"
            onChange={(event) => setName(event.target.value)}
            className="max-w-xs"
            aria-label="Nome no card"
          />

          {preview.isLoading && <SkeletonList rows={2} />}
          {preview.data && <ShareCardPreview card={preview.data} />}

          <Button onClick={() => publish.mutate()} disabled={publish.isPending}>
            <Share2 className="size-4" aria-hidden />
            Publicar link
          </Button>
        </CardContent>
      </Card>

      {cards.data && cards.data.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Links publicados</CardTitle>
            <CardDescription>
              Cada link mostra os números do dia da publicação — e pode ser revogado.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {cards.data.map((item) => (
                <li
                  key={item.public_id}
                  className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2 text-sm last:border-b-0 last:pb-0"
                >
                  <span className="min-w-0 flex-1 truncate">
                    {item.headline}
                    <span className="ml-2 text-xs text-subtle">
                      {new Date(item.created_at).toLocaleDateString('pt-BR')}
                    </span>
                  </span>
                  {item.revoked_at ? (
                    <Badge variant="neutral">revogado</Badge>
                  ) : (
                    <span className="flex gap-2">
                      <Button
                        variant="ghost"
                        onClick={() => {
                          void navigator.clipboard?.writeText(
                            `${window.location.origin}/card/${item.token}`,
                          )
                          toast.success('Link copiado.')
                        }}
                      >
                        Copiar link
                      </Button>
                      <Button variant="ghost" onClick={() => revoke.mutate(item.public_id)}>
                        Revogar
                      </Button>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export function ArenaPage() {
  const duels = useQuery({ queryKey: queryKeys.gameDuels, queryFn: () => gameApi.duels() })

  if (duels.isError) return <ErrorState error={duels.error} onRetry={() => duels.refetch()} />

  return (
    <div className="space-y-6">
      <PageHeader
        title="Arena"
        description="Duelos, eventos, Modo Guerra e o card do seu progresso."
      />

      <Tabs defaultValue="duelos">
        <TabsList>
          <TabsTrigger value="duelos">
            <Swords className="size-4" aria-hidden />
            Duelos
          </TabsTrigger>
          <TabsTrigger value="eventos">Eventos</TabsTrigger>
          <TabsTrigger value="guerra">Modo Guerra</TabsTrigger>
          <TabsTrigger value="card">Card</TabsTrigger>
        </TabsList>

        <TabsContent value="duelos">
          <DuelsTab />
        </TabsContent>
        <TabsContent value="eventos">
          <EventsTab />
        </TabsContent>
        <TabsContent value="guerra">
          <WarTab />
        </TabsContent>
        <TabsContent value="card">
          <CardTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

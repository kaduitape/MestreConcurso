/**
 * Acompanhamento do orquestrador de agentes.
 *
 * A tela precisa deixar uma coisa impossível de confundir: **pulado não é
 * concluído**. Um passo verde que não fez nada é pior que um passo vermelho,
 * porque ninguém investiga o verde. Por isso cada estado tem cor e ícone
 * próprios, e todo passo pulado mostra o motivo escrito ao lado.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Ban,
  Check,
  CircleDashed,
  CirclePlay,
  History,
  Hourglass,
  Link2Off,
  Loader2,
  SkipForward,
  TriangleAlert,
  Workflow,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/feedback/empty-state'
import { SkeletonList } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import { agentsApi } from '@/lib/api/agents'
import { adminCatalogApi } from '@/lib/api/catalog'
import { queryKeys } from '@/lib/query-client'
import type { AgentRun, AgentStep, AgentStepStatus } from '@/lib/api/types'

/**
 * As classes são literais porque o Tailwind 4 só emite a cor que **vê escrita
 * no código** — `text-${x}` montado em tempo de execução sai sem cor. Já
 * aconteceu três vezes neste projeto.
 */
const STATUS: Record<AgentStepStatus, { label: string; icon: LucideIcon; tone: string }> = {
  PENDING: { label: 'Na fila', icon: CircleDashed, tone: 'text-slate-400' },
  RUNNING: { label: 'Rodando', icon: Loader2, tone: 'text-game-cyan' },
  DONE: { label: 'Concluído', icon: Check, tone: 'text-success' },
  DONE_WITH_NOTES: { label: 'Concluído com ressalvas', icon: Check, tone: 'text-warning' },
  SKIPPED: { label: 'Sem o que fazer', icon: SkipForward, tone: 'text-game-orange' },
  // Falta de insumo é o estado que mais precisava sair de "pulado": ele tem
  // ação, e a ação é o que resolve.
  AWAITING_INPUT: { label: 'Aguardando insumo', icon: Hourglass, tone: 'text-game-gold' },
  BLOCKED: { label: 'Bloqueado por dependência', icon: Link2Off, tone: 'text-game-orange' },
  NOT_IMPLEMENTED: { label: 'Não implementado', icon: Ban, tone: 'text-slate-400' },
  FAILED: { label: 'Falhou', icon: TriangleAlert, tone: 'text-danger' },
  BUDGET_BLOCKED: { label: 'Barrado pelo teto', icon: Ban, tone: 'text-game-gold' },
  CANCELED: { label: 'Cancelado', icon: Ban, tone: 'text-slate-400' },
}

const RUN_TONE: Record<string, 'neutral' | 'success' | 'warning' | 'danger' | 'info'> = {
  PENDING: 'neutral',
  RUNNING: 'info',
  DONE: 'success',
  DONE_WITH_NOTES: 'warning',
  FAILED: 'danger',
  CANCELED: 'neutral',
}

const RUN_LABEL: Record<string, string> = {
  PENDING: 'na fila',
  RUNNING: 'rodando',
  DONE: 'concluída',
  DONE_WITH_NOTES: 'concluída com ressalvas',
  FAILED: 'falhou',
  CANCELED: 'cancelada',
}

/** O que cada ação oferece, em português e com destino. */
const ACTION: Record<string, { label: string; hint: string }> = {
  RESOLVE_INPUT: { label: 'Resolver pendência', hint: 'Anexe o PDF ou complete o cadastro' },
  RAISE_BUDGET: { label: 'Ver teto de gasto', hint: 'Ajuste o limite em IA → Orçamento' },
  RETRY_STEP: { label: 'Tentar de novo', hint: 'Roda só este agente' },
  RESOLVE_DEPENDENCY: { label: 'Ver dependência', hint: 'Resolva o passo anterior primeiro' },
}

function duracao(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

/**
 * O histórico de tentativas.
 *
 * É o que respondia errado antes: um passo que falhou duas vezes por motivos
 * diferentes mostrava só o último, e a mensagem de "esgotou as tentativas"
 * apagava os dois. Aqui cada tentativa guarda a própria causa, o próprio
 * código de erro e o id de correlação para cruzar com o log do servidor.
 */
function AttemptHistory({ step }: { step: AgentStep }) {
  const [aberto, setAberto] = useState(false)
  if (step.attempts_history.length === 0) return null

  return (
    <div className="mt-2">
      <button
        type="button"
        className="inline-flex items-center gap-1 text-[0.68rem] text-muted underline-offset-2 hover:underline"
        onClick={() => setAberto((atual) => !atual)}
      >
        <History className="size-3" aria-hidden />
        {aberto ? 'esconder' : 'ver'} o histórico de {step.attempts_history.length} tentativa(s)
      </button>
      {aberto && (
        <ul className="mt-1.5 space-y-1.5 border-l-2 border-border pl-2.5">
          {step.attempts_history.map((tentativa) => (
            <li key={tentativa.number} className="text-[0.68rem]">
              <span className="flex flex-wrap items-center gap-1.5">
                <strong className="text-foreground">#{tentativa.number}</strong>
                <span className={STATUS[tentativa.status]?.tone ?? 'text-muted'}>
                  {STATUS[tentativa.status]?.label ?? tentativa.status}
                </span>
                <span className="text-subtle">{duracao(tentativa.duration_ms)}</span>
                {tentativa.error_code && (
                  <Badge variant="outline">{tentativa.error_code}</Badge>
                )}
                {tentativa.model_slug && (
                  <Badge variant="neutral">
                    {tentativa.provider} · {tentativa.model_slug}
                  </Badge>
                )}
              </span>
              {tentativa.detail && (
                <span className="block text-slate-300">{tentativa.detail}</span>
              )}
              {tentativa.request_id && (
                <span className="block text-subtle">
                  correlação: <code>{tentativa.request_id}</code>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function StepRow({ step, runId }: { step: AgentStep; runId: string }) {
  const queryClient = useQueryClient()
  const visual = STATUS[step.status]
  const Icon = visual.icon

  const runOne = useMutation({
    mutationFn: () => agentsApi.executeOne(runId, step.key),
    onSuccess: (run) => {
      queryClient.setQueryData(queryKeys.agentRun(runId), run)
      const depois = run.steps.find((item) => item.key === step.key)
      const desfecho = depois ? STATUS[depois.status].label.toLowerCase() : 'sem resposta'
      // Um passo que terminou em pendência ou falha não é notícia boa: o aviso
      // segue o resultado do agente, não o fato de a requisição ter dado 200.
      const ruim = depois && ['FAILED', 'BUDGET_BLOCKED'].includes(depois.status)
      const pendente = depois && ['AWAITING_INPUT', 'BLOCKED'].includes(depois.status)
      const mensagem = `${step.label}: ${desfecho}.`
      if (ruim) toast.error(mensagem)
      else if (pendente) toast.warning(mensagem)
      else toast.success(mensagem)
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível rodar o agente.',
      ),
  })

  return (
    <div className="flex flex-wrap items-start gap-3 rounded-lg border border-border p-3">
      <Icon
        className={`mt-0.5 size-4 shrink-0 ${visual.tone} ${
          step.status === 'RUNNING' ? 'animate-spin' : ''
        }`}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-white">
          {step.label}
          <span className={`text-xs font-medium ${visual.tone}`}>{visual.label}</span>
          {!step.is_implemented && (
            // Declarado mas não construído: a tela não deixa isso passar por
            // "ainda não rodou".
            <Badge variant="outline">ainda não existe</Badge>
          )}
        </p>
        <p className="mt-0.5 text-xs text-muted">{step.description}</p>
        {step.detail && <p className="mt-1 text-xs text-slate-300">{step.detail}</p>}
        {step.notes.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {step.notes.map((nota) => (
              <li key={nota} className="text-[0.68rem] text-warning">
                • {nota}
              </li>
            ))}
          </ul>
        )}
        {step.attempts_exhausted && (
          // A mensagem acompanha a causa, em vez de substituí-la: era a
          // substituição que deixava a tela sem diagnóstico.
          <p className="mt-1 text-[0.68rem] text-danger">
            As {step.max_attempts} tentativas automáticas acabaram. A causa acima é a da última;
            o histórico tem as anteriores.
          </p>
        )}
        {step.action && (
          <p className="mt-1 text-[0.68rem] text-game-cyan">
            {ACTION[step.action]?.hint ?? 'Há uma ação para destravar este passo.'}
          </p>
        )}
        {step.depends_on.length > 0 && step.status !== 'BLOCKED' && (
          <p className="mt-1 text-[0.68rem] text-slate-500">
            Depende de: {step.depends_on.join(', ')}
          </p>
        )}
        <AttemptHistory step={step} />
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {step.attempts > 0 && (
          <span
            className="text-[0.68rem] text-muted"
            title={`${step.attempts} de ${step.max_attempts} tentativas`}
          >
            {step.attempts}/{step.max_attempts}
          </span>
        )}
        <Button
          variant="ghost"
          size="sm"
          disabled={runOne.isPending}
          onClick={() => runOne.mutate()}
          title={`Rodar ${step.label} sozinho`}
        >
          <CirclePlay className="size-4" />
        </Button>
      </div>
    </div>
  )
}

/**
 * O identificador cortado não diz nada a quem lê. O nome do concurso e a data
 * dizem — e é por eles que a pessoa procura a execução.
 */
function runLabel(run: AgentRun, competitionNames: Map<string, string>): string {
  const nome = run.competition_public_id
    ? competitionNames.get(run.competition_public_id)
    : undefined
  const quando = new Date(run.created_at).toLocaleDateString('pt-BR')
  return nome ? `${nome} · ${quando}` : `Execução de ${quando}`
}

function RunCard({ run, label }: { run: AgentRun; label: string }) {
  const queryClient = useQueryClient()
  const execute = useMutation({
    mutationFn: () => agentsApi.execute(run.public_id),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.agentRun(run.public_id), updated)
      queryClient.invalidateQueries({ queryKey: ['admin', 'agents'] })
      toast.success('Execução concluída.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível executar.'),
  })

  const reais = (Number(run.cost_cents) / 100).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">{label}</CardTitle>
            <CardDescription>
              Custo desta execução: {reais}
              {run.finished_at ? ' · encerrada' : ''}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={RUN_TONE[run.status] ?? 'neutral'}>
              {RUN_LABEL[run.status] ?? run.status}
            </Badge>
            <Button onClick={() => execute.mutate()} disabled={execute.isPending}>
              <CirclePlay className="size-4" /> Executar tudo
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {run.steps.map((step) => (
          <StepRow key={step.key} step={step} runId={run.public_id} />
        ))}
      </CardContent>
    </Card>
  )
}

export function AgentsSection() {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)
  const [competition, setCompetition] = useState('')

  const params = { page: 1, page_size: 20 }
  const runs = useQuery({
    queryKey: queryKeys.agentRuns(params),
    queryFn: () => agentsApi.runs(params),
  })
  const catalog = useQuery({ queryKey: queryKeys.agentCatalog, queryFn: agentsApi.catalog })
  const competitions = useQuery({
    queryKey: ['admin', 'catalog', 'competitions', 'for-agents'],
    queryFn: () => adminCatalogApi.competitions({ page: 1, page_size: 50 }),
  })
  const detail = useQuery({
    queryKey: queryKeys.agentRun(selected ?? ''),
    queryFn: () => agentsApi.run(selected!),
    enabled: Boolean(selected),
    // Enquanto roda, a tela se atualiza sozinha: o worker está em outro
    // processo e o estado mora no banco.
    refetchInterval: (query) => (query.state.data?.status === 'RUNNING' ? 2000 : false),
  })

  const create = useMutation({
    mutationFn: () => agentsApi.create(competition),
    onSuccess: (run) => {
      setSelected(run.public_id)
      queryClient.invalidateQueries({ queryKey: ['admin', 'agents'] })
      toast.success('Execução criada.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível criar.'),
  })

  const nomes = new Map(
    (competitions.data?.items ?? []).map((item) => [
      item.public_id,
      `${item.name} (${item.year})`,
    ]),
  )
  const agentes = catalog.data?.agents ?? []
  const construidos = agentes.filter((item) => item.is_implemented)
  const naoConstruidos = agentes.filter((item) => !item.is_implemented)

  return (
    <div className="space-y-6">
      <Alert tone="info" title="Agente que não existe não aparece verde">
        Agente sem implementação fica <strong>pulado, com o motivo escrito</strong> — nunca
        concluído. Um passo verde que não fez nada é pior que um passo vermelho, porque ninguém
        investiga o verde.
        {agentes.length > 0 && (
          <>
            {' '}
            Hoje {construidos.length} dos {agentes.length} agentes rodam, reaproveitando
            serviços que já estavam no ar.
          </>
        )}
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Workflow /> Nova execução
          </CardTitle>
          <CardDescription>
            Roda os agentes sobre um concurso, na ordem das dependências.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <label className="min-w-[260px] flex-1">
            <span className="game-label mb-1 block text-[0.6rem] text-muted">Concurso</span>
            <select
              className="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground"
              value={competition}
              onChange={(event) => setCompetition(event.target.value)}
            >
              <option value="">— escolha —</option>
              {(competitions.data?.items ?? []).map((item) => (
                <option key={item.public_id} value={item.public_id}>
                  {item.name} ({item.year})
                </option>
              ))}
            </select>
          </label>
          <Button onClick={() => create.mutate()} disabled={!competition || create.isPending}>
            Criar execução
          </Button>
        </CardContent>
      </Card>

      {naoConstruidos.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Agentes ainda não construídos</CardTitle>
            <CardDescription>
              Declarados no catálogo, pulados na execução. Cada um diz por quê.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {naoConstruidos.map((item) => (
              <div key={item.key} className="rounded-lg border border-dashed border-border p-3">
                <p className="text-sm font-semibold text-white">{item.label}</p>
                <p className="mt-0.5 text-xs text-muted">{item.pending_reason}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {runs.isLoading && <SkeletonList rows={3} />}
      {runs.data?.items.length === 0 && (
        <EmptyState
          icon={Workflow}
          title="Nenhuma execução ainda"
          description="Escolha um concurso acima para rodar os agentes."
        />
      )}

      <div className="space-y-2">
        {runs.data?.items.map((run) => (
          <button
            key={run.public_id}
            type="button"
            onClick={() => setSelected(run.public_id)}
            className={`w-full rounded-lg border p-3 text-left transition ${
              selected === run.public_id
                ? 'border-game-gold/60 bg-game-gold/10'
                : 'border-border hover:border-game-gold/35'
            }`}
          >
            <span className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-white">{runLabel(run, nomes)}</span>
              <Badge variant={RUN_TONE[run.status] ?? 'neutral'}>
                {RUN_LABEL[run.status] ?? run.status}
              </Badge>
            </span>
          </button>
        ))}
      </div>

      {detail.data && <RunCard run={detail.data} label={runLabel(detail.data, nomes)} />}
    </div>
  )
}

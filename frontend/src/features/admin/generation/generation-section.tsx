/**
 * Geração em massa por tópico.
 *
 * A tela tem uma obrigação acima das outras: **a estimativa não pode parecer
 * mais certa do que é**. Quando falta histórico medido, ela diz isso com todas
 * as letras em vez de mostrar um número — confirmar um plano de centenas de
 * tópicos acreditando num chute é como a fatura surpreende.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, Check, CircleDashed, Play, Recycle, TriangleAlert, Wand } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/feedback/empty-state'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import { adminCatalogApi } from '@/lib/api/catalog'
import { generationApi } from '@/lib/api/generation'
import { queryKeys } from '@/lib/query-client'
import type { GenerationItemStatus, GenerationPlan } from '@/lib/api/types'

/**
 * Classes literais: o Tailwind 4 só emite a cor que vê escrita no código.
 */
const ITEM: Record<GenerationItemStatus, { label: string; icon: LucideIcon; tone: string }> = {
  PENDING: { label: 'Na fila', icon: CircleDashed, tone: 'text-slate-400' },
  DONE: { label: 'Rascunho gerado', icon: Check, tone: 'text-success' },
  REUSED: { label: 'Reaproveitado', icon: Recycle, tone: 'text-game-cyan' },
  FAILED: { label: 'Falhou', icon: TriangleAlert, tone: 'text-danger' },
  BUDGET_BLOCKED: { label: 'Barrado pelo teto', icon: Ban, tone: 'text-game-gold' },
  CANCELED: { label: 'Cancelado', icon: Ban, tone: 'text-muted' },
}

const PLAN_TONE: Record<string, 'neutral' | 'info' | 'success' | 'danger' | 'warning'> = {
  DRAFT: 'neutral',
  CONFIRMED: 'info',
  RUNNING: 'info',
  DONE: 'success',
  CANCELED: 'neutral',
}

const KIND_LABEL: Record<string, string> = {
  TRAINING_LESSON: 'Aula',
  MIND_MAP: 'Mapa mental',
}

function reais(cents: string): string {
  return (Number(cents) / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

/** Plural certo: "1 item" e "2 itens" — texto torto tira a confiança do número. */
function itens(quantos: number): string {
  return quantos === 1 ? '1 item' : `${quantos} itens`
}

function Estimate({ plan }: { plan: GenerationPlan }) {
  const aGerar = plan.items.filter((item) => item.decision === 'GENERATE').length
  const faltando = plan.estimate_basis.unknown_features ?? []

  if (!plan.estimate_is_known) {
    return (
      <Alert tone="warning" title="Não dá para estimar o custo deste plano">
        {faltando.length > 0 && (
          <>
            Falta histórico medido de: <strong>{faltando.join(', ')}</strong>.{' '}
          </>
        )}
        {Number(plan.estimate_cents) > 0 && (
          <>
            O que deu para estimar soma {reais(plan.estimate_cents)}, e esse número está{' '}
            <strong>incompleto</strong>.{' '}
          </>
        )}
        Gerar {itens(aGerar)} vai custar — só não dá para dizer quanto antes de medir algumas
        execuções. Rodar um plano pequeno primeiro é o caminho.
      </Alert>
    )
  }

  return (
    <Alert tone="info" title={`Estimativa: ${reais(plan.estimate_cents)}`}>
      Para {itens(aGerar)} a gerar, a partir da <strong>mediana do custo medido</strong> das
      execuções anteriores. É estimativa, não contrato: o custo real de cada chamada só é
      conhecido depois dela.
    </Alert>
  )
}

function PlanCard({ plan }: { plan: GenerationPlan }) {
  const queryClient = useQueryClient()
  const [aberto, setAberto] = useState(false)

  const confirmar = useMutation({
    mutationFn: () => generationApi.confirm(plan.public_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'generation'] })
      toast.success('Plano confirmado. A geração começou.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível confirmar.'),
  })
  const cancelar = useMutation({
    mutationFn: () => generationApi.cancel(plan.public_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'generation'] })
      toast.success('Plano cancelado.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível cancelar.'),
  })

  const aGerar = plan.items.filter((item) => item.decision === 'GENERATE').length
  const reaproveitados = plan.items.length - aGerar

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">
              {plan.kinds.map((kind) => KIND_LABEL[kind] ?? kind).join(' e ')} ·{' '}
              {itens(plan.items.length)}
            </CardTitle>
            <CardDescription>
              {aGerar} a gerar, {reaproveitados}{' '}
              {reaproveitados === 1 ? 'já existe' : 'já existem'} ·{' '}
              {new Date(plan.created_at).toLocaleDateString('pt-BR')}
              {Number(plan.spent_cents) > 0 && <> · gasto real: {reais(plan.spent_cents)}</>}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={PLAN_TONE[plan.status] ?? 'neutral'}>{plan.status}</Badge>
            {plan.status === 'DRAFT' && (
              <>
                <Button variant="ghost" size="sm" onClick={() => cancelar.mutate()}>
                  Descartar
                </Button>
                <Button onClick={() => confirmar.mutate()} disabled={confirmar.isPending}>
                  <Play className="size-4" /> Confirmar e gerar
                </Button>
              </>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {plan.status === 'DRAFT' && <Estimate plan={plan} />}

        {plan.progress.total > 0 && plan.status !== 'DRAFT' && (
          <p className="text-sm text-slate-300">
            {plan.progress.done} rascunhos gerados · {plan.progress.reused} reaproveitados ·{' '}
            {plan.progress.pending} na fila
            {plan.progress.failed > 0 && <> · {plan.progress.failed} falharam</>}
            {plan.progress.blocked > 0 && (
              <>
                {' '}
                · <strong className="text-game-gold">{plan.progress.blocked} barrados</strong>
              </>
            )}
          </p>
        )}

        <button
          type="button"
          className="text-xs text-muted underline-offset-2 hover:underline"
          onClick={() => setAberto((valor) => !valor)}
        >
          {aberto ? 'Esconder os itens' : `Ver ${itens(plan.items.length)}`}
        </button>

        {aberto && (
          <ul className="space-y-1.5">
            {plan.items.map((item, index) => {
              const visual = ITEM[item.status]
              const Icon = visual.icon
              return (
                <li
                  key={`${item.topic_name}-${item.kind}-${index}`}
                  className="flex items-start gap-2 rounded-md border border-border p-2"
                >
                  <Icon className={`mt-0.5 size-3.5 shrink-0 ${visual.tone}`} aria-hidden />
                  <span className="min-w-0 flex-1 text-xs">
                    <span className="font-semibold text-white">{item.topic_name}</span>{' '}
                    <span className="text-muted">
                      ({item.subject_name} · {KIND_LABEL[item.kind] ?? item.kind})
                    </span>
                    <span className={`ml-2 font-medium ${visual.tone}`}>{visual.label}</span>
                    {item.reason && <span className="block text-slate-400">{item.reason}</span>}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export function GenerationSection() {
  const queryClient = useQueryClient()
  const [competition, setCompetition] = useState('')
  const [kinds, setKinds] = useState<string[]>(['TRAINING_LESSON'])

  const params = { page: 1, page_size: 10 }
  const plans = useQuery({
    queryKey: queryKeys.generationPlans(params),
    queryFn: () => generationApi.plans(params),
    // Enquanto roda, a tela se atualiza sozinha: quem gera é o worker.
    refetchInterval: (query) =>
      query.state.data?.items.some((plan) => plan.status === 'RUNNING') ? 4000 : false,
  })
  const competitions = useQuery({
    queryKey: ['admin', 'catalog', 'competitions', 'for-generation'],
    queryFn: () => adminCatalogApi.competitions({ page: 1, page_size: 50 }),
  })

  const montar = useMutation({
    mutationFn: () => generationApi.create({ competition_public_id: competition, kinds }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'generation'] })
      toast.success('Plano montado. Nada foi gerado ainda.')
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível montar o plano.',
      ),
  })

  function alternar(kind: string) {
    setKinds((atual) =>
      atual.includes(kind) ? atual.filter((item) => item !== kind) : [...atual, kind],
    )
  }

  return (
    <div className="space-y-6">
      <Alert tone="info" title="Montar o plano não gasta nada">
        O plano mostra o que seria gerado, o que já existe e quanto deve custar. A geração só
        começa quando <strong>uma pessoa confirma</strong> — e o que sai dela é{' '}
        <strong>rascunho</strong>: conteúdo de IA que ninguém conferiu não passa pelo portão de
        qualidade.
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wand /> Novo plano
          </CardTitle>
          <CardDescription>
            Um item por tópico do edital analisado. Tópico que já tem conteúdo é reaproveitado,
            inclusive de outro concurso.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <label className="min-w-[260px] flex-1">
            <span className="game-label mb-1 block text-[0.6rem] text-muted">Concurso</span>
            <Select
              value={competition}
              onChange={(event) => setCompetition(event.target.value)}
            >
              <option value="">— escolha —</option>
              {(competitions.data?.items ?? []).map((item) => (
                <option key={item.public_id} value={item.public_id}>
                  {item.name} ({item.year})
                </option>
              ))}
            </Select>
          </label>
          <div className="flex items-center gap-2">
            {Object.entries(KIND_LABEL).map(([kind, label]) => (
              <Button
                key={kind}
                type="button"
                variant={kinds.includes(kind) ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => alternar(kind)}
              >
                {label}
              </Button>
            ))}
          </div>
          <Button
            onClick={() => montar.mutate()}
            disabled={!competition || kinds.length === 0 || montar.isPending}
          >
            Montar plano
          </Button>
        </CardContent>
      </Card>

      {plans.isLoading && <SkeletonList rows={2} />}
      {plans.data?.items.length === 0 && (
        <EmptyState
          icon={Wand}
          title="Nenhum plano ainda"
          description="Escolha um concurso acima para ver o que seria gerado."
        />
      )}
      {(plans.data?.items ?? []).map((plan) => (
        <PlanCard key={plan.public_id} plan={plan} />
      ))}
    </div>
  )
}

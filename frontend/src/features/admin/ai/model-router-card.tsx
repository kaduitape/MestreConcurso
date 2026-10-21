/**
 * O roteador de modelos na tela.
 *
 * Três coisas esta tela não pode deixar passar:
 *
 * 1. **"Não avaliada" não é "não atendeu".** Uma regra que depende de um sinal
 *    que a chamada não informou aparece com cor e rótulo próprios. Mostrá-la
 *    como "não atendeu" afirmaria uma comparação que ninguém fez.
 * 2. **Regra com modelo indisponível fica à vista.** Ela está ligada e não
 *    serve para nada; esconder isso faria o administrador acreditar numa
 *    configuração que não vale.
 * 3. **Cada decisão mostra o rastro inteiro**, não só a regra vencedora — é a
 *    única forma de responder por que as outras não venceram.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleHelp, CircleSlash, Plus, Route, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { Toggle } from '@/components/ui/toggle'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { aiApi } from '@/lib/api/ai'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/query-client'
import type {
  AIFeatureBinding,
  AIModelRoute,
  AIProvider,
  AIRouteOutcome,
  AIRouteReason,
  AIRoutingDecision,
} from '@/lib/api/types'

/**
 * Classes literais: o Tailwind 4 só emite a cor que **vê escrita no código**.
 * `text-${x}` montado em tempo de execução sai sem cor.
 */
const OUTCOME: Record<AIRouteOutcome, { label: string; tone: string }> = {
  MATCHED: { label: 'atendeu', tone: 'text-success' },
  NOT_MATCHED: { label: 'não atendeu', tone: 'text-muted' },
  NOT_EVALUATED: { label: 'não avaliada', tone: 'text-game-cyan' },
  DISABLED: { label: 'desligada', tone: 'text-danger' },
  UNUSABLE: { label: 'modelo indisponível', tone: 'text-game-orange' },
}

const REASON: Record<AIRouteReason, { label: string; variant: 'success' | 'warning' | 'outline' }> =
  {
    RULE_MATCHED: { label: 'regra aplicada', variant: 'success' },
    BINDING_DEFAULT: { label: 'vínculo da funcionalidade', variant: 'outline' },
    FALLBACK_AFTER_ERROR: { label: 'reserva depois de erro', variant: 'warning' },
  }

const SIGNAL_LABEL: Record<string, string> = {
  INPUT_CHARS: 'tamanho da entrada',
  NEEDS_JSON: 'exige JSON',
  BUDGET_USED_PCT: 'percentual do teto gasto',
}

const SIGNAL_VALUE_LABEL: Record<string, string> = {
  input_chars: 'entrada',
  needs_json: 'JSON',
  budget_used_pct: 'teto gasto',
}

function milhar(valor: number) {
  return valor.toLocaleString('pt-BR')
}

function condicoesDe(route: AIModelRoute): string[] {
  const partes: string[] = []
  if (route.min_input_chars !== null) {
    partes.push(`entrada ≥ ${milhar(route.min_input_chars)} caracteres`)
  }
  if (route.max_input_chars !== null) {
    partes.push(`entrada ≤ ${milhar(route.max_input_chars)} caracteres`)
  }
  if (route.requires_json !== null) {
    partes.push(route.requires_json ? 'exige JSON' : 'não exige JSON')
  }
  if (route.min_budget_used_pct !== null) {
    partes.push(`teto mensal ≥ ${route.min_budget_used_pct}% gasto`)
  }
  return partes
}

function RuleRow({ route }: { route: AIModelRoute }) {
  const queryClient = useQueryClient()
  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'ai', 'routes'] })
  }

  const salvar = useMutation({
    mutationFn: (input: { is_enabled: boolean }) => aiApi.updateRoute(route.id, input),
    onSuccess: () => {
      invalidar()
      toast.success('Regra atualizada.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  const remover = useMutation({
    mutationFn: () => aiApi.deleteRoute(route.id),
    onSuccess: () => {
      invalidar()
      toast.success('Regra removida.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível remover.'),
  })

  const condicoes = condicoesDe(route)

  return (
    <div
      className={`rounded-lg border p-3 ${
        route.is_enabled ? 'border-border' : 'border-dashed border-border/60'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-white">
            {route.label}
            <Badge variant="outline">prioridade {route.priority}</Badge>
            {!route.is_enabled && <Badge variant="outline">desligada</Badge>}
            {route.is_enabled && !route.model_is_usable && (
              /* Ligada e inútil: o modelo dela não está disponível. */
              <Badge variant="warning">modelo indisponível</Badge>
            )}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {route.feature_label} → <span className="font-mono">{route.model_slug ?? '—'}</span>
            {route.provider_slug && ` · ${route.provider_slug}`}
          </p>
          <p className="mt-1 text-[0.68rem] text-slate-500">
            {condicoes.length === 0
              ? 'sem condição: vale para toda chamada da funcionalidade'
              : condicoes.join(' e ')}
          </p>
          {route.required_signals.length > 0 && (
            <p className="mt-0.5 text-[0.68rem] text-slate-500">
              Depende de: {route.required_signals.map((item) => SIGNAL_LABEL[item] ?? item).join(', ')}
              {' — '}a chamada que não informar isso deixa a regra sem avaliação.
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Toggle
            checked={route.is_enabled}
            disabled={salvar.isPending}
            label={`Ligar a regra ${route.label}`}
            onChange={(valor) => salvar.mutate({ is_enabled: valor })}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            loading={remover.isPending}
            aria-label={`Remover a regra ${route.label}`}
            onClick={() => remover.mutate()}
          >
            <Trash2 />
          </Button>
        </div>
      </div>
    </div>
  )
}

function NewRuleForm({
  features,
  providers,
  onDone,
}: {
  features: AIFeatureBinding[]
  providers: AIProvider[]
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const roteaveis = features.filter((item) => item.is_routable)
  const [feature, setFeature] = useState(roteaveis[0]?.feature ?? '')
  const [label, setLabel] = useState('')
  const [priority, setPriority] = useState('100')
  const [alvo, setAlvo] = useState('')
  const [minChars, setMinChars] = useState('')
  const [maxChars, setMaxChars] = useState('')
  const [json, setJson] = useState('')
  const [pct, setPct] = useState('')

  const modelos = providers.flatMap((provider) =>
    provider.models
      .filter((model) => model.is_active && model.kind !== 'embedding')
      .map((model) => ({
        value: `${provider.slug}::${model.slug}`,
        label: `${model.slug} · ${provider.display_name}`,
      })),
  )

  const criar = useMutation({
    mutationFn: () => {
      const [providerSlug, modelSlug] = alvo.split('::')
      return aiApi.createRoute({
        feature,
        label: label.trim(),
        priority: Number(priority) || 0,
        is_enabled: true,
        provider_slug: providerSlug,
        model_slug: modelSlug,
        min_input_chars: minChars === '' ? null : Number(minChars),
        max_input_chars: maxChars === '' ? null : Number(maxChars),
        requires_json: json === '' ? null : json === 'true',
        min_budget_used_pct: pct === '' ? null : Number(pct),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'ai', 'routes'] })
      toast.success('Regra cadastrada.')
      onDone()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível cadastrar.'),
  })

  const incompleta = !feature || label.trim().length < 3 || !alvo

  return (
    <form
      className="space-y-3 rounded-lg border border-dashed border-border p-3"
      onSubmit={(event) => {
        event.preventDefault()
        if (!incompleta) criar.mutate()
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-muted">
          Funcionalidade
          <Select
            className="mt-1"
            value={feature}
            aria-label="Funcionalidade da regra"
            onChange={(event) => setFeature(event.target.value)}
          >
            {roteaveis.map((item) => (
              <option key={item.feature} value={item.feature}>
                {item.label}
              </option>
            ))}
          </Select>
        </label>
        <label className="text-xs text-muted">
          Modelo que atende
          <Select
            className="mt-1"
            value={alvo}
            aria-label="Modelo da regra"
            onChange={(event) => setAlvo(event.target.value)}
          >
            <option value="">{modelos.length ? 'escolha um modelo' : 'nenhum modelo ativo'}</option>
            {modelos.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
        </label>
        <label className="text-xs text-muted">
          Nome da regra
          <Input
            className="mt-1"
            value={label}
            placeholder="Edital grande"
            aria-label="Nome da regra"
            onChange={(event) => setLabel(event.target.value)}
          />
        </label>
        <label className="text-xs text-muted">
          Prioridade (menor decide primeiro)
          <Input
            className="mt-1"
            type="number"
            min={0}
            max={1000}
            value={priority}
            aria-label="Prioridade da regra"
            onChange={(event) => setPriority(event.target.value)}
          />
        </label>
      </div>

      <p className="text-[0.68rem] text-slate-500">
        Condições em branco não condicionam. Todas as preenchidas precisam valer ao mesmo tempo —
        e uma regra sem condição nenhuma vale para toda chamada da funcionalidade.
      </p>

      <div className="grid gap-3 sm:grid-cols-4">
        <label className="text-xs text-muted">
          Entrada mínima
          <Input
            className="mt-1"
            type="number"
            min={0}
            value={minChars}
            placeholder="caracteres"
            aria-label="Tamanho mínimo da entrada"
            onChange={(event) => setMinChars(event.target.value)}
          />
        </label>
        <label className="text-xs text-muted">
          Entrada máxima
          <Input
            className="mt-1"
            type="number"
            min={0}
            value={maxChars}
            placeholder="caracteres"
            aria-label="Tamanho máximo da entrada"
            onChange={(event) => setMaxChars(event.target.value)}
          />
        </label>
        <label className="text-xs text-muted">
          Resposta em JSON
          <Select
            className="mt-1"
            value={json}
            aria-label="Exigência de JSON"
            onChange={(event) => setJson(event.target.value)}
          >
            <option value="">não condiciona</option>
            <option value="true">só quando exige</option>
            <option value="false">só quando não exige</option>
          </Select>
        </label>
        <label className="text-xs text-muted">
          Teto mensal gasto (%)
          <Input
            className="mt-1"
            type="number"
            min={0}
            max={999}
            value={pct}
            placeholder="80"
            aria-label="Percentual mínimo do teto mensal gasto"
            onChange={(event) => setPct(event.target.value)}
          />
        </label>
      </div>

      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" loading={criar.isPending} disabled={incompleta}>
          Cadastrar regra
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onDone}>
          Cancelar
        </Button>
      </div>
    </form>
  )
}

function DecisionCard({ decision }: { decision: AIRoutingDecision }) {
  const motivo = REASON[decision.reason]
  const naoAvaliadas = decision.trace.filter((item) => item.outcome === 'NOT_EVALUATED')
  const sinais = Object.entries(decision.signals)

  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-white">
          {decision.feature_label} → <span className="font-mono text-xs">{decision.model_slug}</span>
        </p>
        <Badge variant={motivo.variant}>{motivo.label}</Badge>
      </div>
      <p className="mt-0.5 text-[0.68rem] text-slate-500">
        {new Date(decision.created_at).toLocaleString('pt-BR')} · {decision.provider_slug}
      </p>
      <p className="mt-1 text-xs text-slate-300">{decision.explanation}</p>

      <p className="mt-2 text-[0.68rem] text-slate-500">
        {sinais.length === 0 ? (
          /* Nenhum sinal informado é um fato sobre a chamada, não um detalhe
             a esconder: é o que explica toda regra ficar sem avaliação. */
          <>Esta chamada não informou nenhum sinal.</>
        ) : (
          <>
            Sinais informados:{' '}
            {sinais
              .map(
                ([chave, valor]) =>
                  `${SIGNAL_VALUE_LABEL[chave] ?? chave}: ${
                    typeof valor === 'boolean' ? (valor ? 'sim' : 'não') : valor
                  }`,
              )
              .join(' · ')}
          </>
        )}
      </p>

      {decision.trace.length > 0 && (
        <ul className="mt-2 space-y-1">
          {decision.trace.map((item) => {
            const visual = OUTCOME[item.outcome]
            return (
              <li key={item.rule_id} className="flex items-start gap-2 text-xs">
                {item.outcome === 'NOT_EVALUATED' ? (
                  <CircleHelp className="mt-0.5 size-3.5 shrink-0 text-game-cyan" aria-hidden />
                ) : (
                  <CircleSlash
                    className={`mt-0.5 size-3.5 shrink-0 ${
                      item.outcome === 'MATCHED' ? 'text-success' : 'text-slate-500'
                    }`}
                    aria-hidden
                  />
                )}
                <span className="text-slate-300">
                  <span className={`font-semibold ${visual.tone}`}>
                    {item.label} — {visual.label}:
                  </span>{' '}
                  {item.detail}
                </span>
              </li>
            )
          })}
        </ul>
      )}

      {naoAvaliadas.length > 0 && (
        <p className="mt-2 text-[0.68rem] text-game-cyan">
          {naoAvaliadas.length === 1
            ? '1 regra ficou sem avaliação por falta de sinal — não foi comparada e não reprovou.'
            : `${naoAvaliadas.length} regras ficaram sem avaliação por falta de sinal — não foram comparadas e não reprovaram.`}
        </p>
      )}
    </div>
  )
}

/** Regras do roteador e o histórico de escolhas. */
export function ModelRouterCard({ providers }: { providers: AIProvider[] }) {
  const [novo, setNovo] = useState(false)
  const [filtro, setFiltro] = useState('')

  const features = useQuery({ queryKey: queryKeys.aiFeatures, queryFn: aiApi.features })
  const routes = useQuery({
    queryKey: queryKeys.aiRoutes(filtro || undefined),
    queryFn: () => aiApi.routes(filtro || undefined),
  })
  const decisions = useQuery({
    queryKey: queryKeys.aiRouteDecisions(filtro || undefined),
    queryFn: () => aiApi.routeDecisions(filtro || undefined),
  })

  const roteaveis = (features.data ?? []).filter((item) => item.is_routable)
  const ligadasSemModelo = (routes.data ?? []).filter(
    (item) => item.is_enabled && !item.model_is_usable,
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Roteador de modelos</CardTitle>
        <CardDescription>
          Sem regra, cada funcionalidade usa o modelo vinculado a ela. Com regra, a plataforma
          escolhe por sinais que ela <strong>mede</strong> — tamanho da entrada, exigência de JSON,
          percentual do teto mensal já gasto. Nenhuma IA participa dessa escolha.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <Alert tone="info" title="Sinal que a chamada não informa deixa a regra sem avaliação">
          Uma regra sobre o tamanho da entrada só vale nas funcionalidades que informam esse
          tamanho. Nas outras ela fica <strong>não avaliada</strong> — e aparece assim no
          histórico, em vez de contar como "não atendeu". Sem teto mensal cadastrado não existe
          percentual do teto, e regras de orçamento também ficam sem avaliação.
        </Alert>

        {ligadasSemModelo.length > 0 && (
          <Alert tone="warning" title="Regra ligada apontando para modelo indisponível">
            {ligadasSemModelo.map((item) => item.label).join(', ')} —{' '}
            {ligadasSemModelo.length === 1 ? 'esta regra' : 'estas regras'} nunca se aplica
            {ligadasSemModelo.length === 1 ? '' : 'm'}: o modelo está inativo, sem chave ou com o
            provedor desligado.
          </Alert>
        )}

        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-muted">
            Funcionalidade
            <Select
              className="mt-1 w-64"
              value={filtro}
              aria-label="Filtrar por funcionalidade"
              onChange={(event) => setFiltro(event.target.value)}
            >
              <option value="">todas</option>
              {roteaveis.map((item) => (
                <option key={item.feature} value={item.feature}>
                  {item.label}
                </option>
              ))}
            </Select>
          </label>
          {!novo && (
            <Button
              type="button"
              size="sm"
              disabled={roteaveis.length === 0}
              onClick={() => setNovo(true)}
            >
              <Plus /> Nova regra
            </Button>
          )}
        </div>

        {novo && (
          <NewRuleForm
            features={features.data ?? []}
            providers={providers}
            onDone={() => setNovo(false)}
          />
        )}

        {routes.isLoading && <SkeletonList rows={2} />}
        {routes.isError && <ErrorState error={routes.error} onRetry={() => routes.refetch()} />}
        {routes.data?.length === 0 && (
          <EmptyState
            icon={Route}
            title="Nenhuma regra cadastrada"
            description="Cada funcionalidade usa o modelo vinculado a ela, e o histórico registra isso em toda chamada."
          />
        )}
        {(routes.data ?? []).length > 0 && (
          <div className="space-y-2">
            {routes.data?.map((route) => <RuleRow key={route.id} route={route} />)}
          </div>
        )}

        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-white">Por que cada modelo foi usado</h3>
          <p className="text-[0.68rem] text-slate-500">
            Uma linha por chamada de IA, com o rastro de todas as regras avaliadas — não só da
            vencedora.
          </p>
          {decisions.isLoading && <SkeletonList rows={2} />}
          {decisions.isError && (
            <ErrorState error={decisions.error} onRetry={() => decisions.refetch()} />
          )}
          {decisions.data?.length === 0 && (
            <p className="text-xs text-muted">
              Nenhuma chamada de IA registrada ainda — o histórico começa na primeira.
            </p>
          )}
          {decisions.data?.map((decision) => (
            <DecisionCard key={decision.id} decision={decision} />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

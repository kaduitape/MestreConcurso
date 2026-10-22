/**
 * O analista de melhorias (Agente 8) na tela.
 *
 * Quatro coisas esta tela não pode deixar passar:
 *
 * 1. **Nenhum botão aplica nada.** O analista propõe; a correção é feita nas
 *    telas que já existem. Um botão "aplicar" aqui seria exatamente a
 *    modificação autônoma que o desenho proibiu.
 * 2. **"Não rodou por falta de amostra" não é "está tudo certo".** O detector
 *    que não pôde rodar aparece com cor e texto próprios, nunca como limpo.
 * 3. **Isolamento declarado como ele é.** `CODE_ONLY` não pode parecer
 *    `DB_READONLY`: a tela diz quando a garantia é apenas do código.
 * 4. **Economia só com número medido.** O valor aparece quando existe custo
 *    medido; sem ele, nada é afirmado.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CircleHelp,
  Lightbulb,
  Play,
  ShieldCheck,
  ShieldAlert,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
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
import { ApiError } from '@/lib/api/client'
import { improvementsApi } from '@/lib/api/improvements'
import { queryKeys } from '@/lib/query-client'
import type {
  ImprovementDetector,
  ImprovementDetectorStatus,
  ImprovementFinding,
  ImprovementRun,
  ImprovementSeverity,
} from '@/lib/api/types'

/**
 * Classes literais: o Tailwind 4 só emite a cor que **vê escrita no código**.
 * `text-${x}` montado em tempo de execução sai sem cor.
 */
const SEVERITY: Record<ImprovementSeverity, { label: string; variant: 'danger' | 'warning' | 'outline' }> =
  {
    HIGH: { label: 'alta', variant: 'danger' },
    MEDIUM: { label: 'média', variant: 'warning' },
    LOW: { label: 'baixa', variant: 'outline' },
  }

const DETECTOR_STATUS: Record<
  ImprovementDetectorStatus,
  { label: string; icon: LucideIcon; tone: string }
> = {
  FOUND: { label: 'achou', icon: Lightbulb, tone: 'text-game-gold' },
  CLEAN: { label: 'conferiu e não achou', icon: ShieldCheck, tone: 'text-success' },
  NOT_ENOUGH_DATA: { label: 'sem amostra para rodar', icon: CircleHelp, tone: 'text-game-cyan' },
  DISABLED: { label: 'desligado', icon: ShieldAlert, tone: 'text-muted' },
}

const STATUS_LABEL: Record<string, string> = {
  OPEN: 'aberto',
  ACCEPTED: 'aceito',
  REJECTED: 'recusado',
  RESOLVED: 'fechado pelo detector',
}

const DESTINATION_LABEL: Record<string, string> = {
  ADMIN: 'há tela para resolver',
  DEVELOPMENT: 'precisa de código',
}

function reais(centavos: string | null) {
  if (centavos === null) return null
  const valor = Number(centavos) / 100
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function IsolationBadge({ isolation }: { isolation: ImprovementRun['isolation'] }) {
  if (isolation === 'DB_READONLY') {
    return <Badge variant="success">credencial restrita de banco em uso</Badge>
  }
  // Não pode parecer isolado: a garantia aqui é só do código.
  return <Badge variant="warning">sem credencial restrita — garantia só do código</Badge>
}

function FindingCard({ finding }: { finding: ImprovementFinding }) {
  const queryClient = useQueryClient()
  const [motivo, setMotivo] = useState('')
  const [recusando, setRecusando] = useState(false)
  const severidade = SEVERITY[finding.severity]
  const desperdicio = reais(finding.measured_waste_cents)

  const decidir = useMutation({
    mutationFn: (input: { status: string; reason?: string }) =>
      improvementsApi.decide(finding.public_id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'improvements'] })
      toast.success('Decisão registrada.')
      setRecusando(false)
      setMotivo('')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível registrar.'),
  })

  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-sm font-semibold text-white">{finding.title}</p>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Badge variant={severidade.variant}>{severidade.label}</Badge>
          <Badge variant="outline">{STATUS_LABEL[finding.status] ?? finding.status}</Badge>
        </div>
      </div>
      <p className="mt-0.5 text-[0.68rem] text-slate-500">
        {finding.detector_label} · {DESTINATION_LABEL[finding.destination] ?? finding.destination}{' '}
        · visto {finding.seen_count}×
        {finding.reopened_count > 0 && ` · reaberto ${finding.reopened_count}×`}
      </p>

      <p className="mt-2 text-xs text-slate-300">{finding.detail}</p>
      <p className="mt-2 text-xs text-game-gold">
        <strong>Proposta:</strong> {finding.proposal}
      </p>
      {desperdicio && (
        <p className="mt-1 text-xs text-danger">Gasto medido no problema: {desperdicio}</p>
      )}

      {finding.decision_reason && (
        <p className="mt-2 text-[0.68rem] text-slate-500">
          Motivo registrado: {finding.decision_reason}
        </p>
      )}
      {finding.muted_until && (
        <p className="mt-0.5 text-[0.68rem] text-slate-500">
          Recusado: não volta até {new Date(finding.muted_until).toLocaleDateString('pt-BR')}.
        </p>
      )}

      {(finding.status === 'OPEN' || finding.status === 'ACCEPTED') && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            {finding.status === 'OPEN' && (
              <Button
                type="button"
                size="sm"
                loading={decidir.isPending}
                onClick={() => decidir.mutate({ status: 'ACCEPTED' })}
              >
                <ThumbsUp /> Vou fazer
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRecusando((atual) => !atual)}
            >
              <ThumbsDown /> Recusar
            </Button>
            {/* Nenhum botão aplica a mudança: a correção é feita na tela que
                cuida daquilo. O analista não mexe em produção. */}
            <span className="text-[0.68rem] text-slate-500">
              A correção é feita na tela correspondente — o analista não aplica nada.
            </span>
          </div>
          {recusando && (
            <form
              className="flex flex-wrap items-center gap-2"
              onSubmit={(event) => {
                event.preventDefault()
                decidir.mutate({ status: 'REJECTED', reason: motivo })
              }}
            >
              <Input
                className="h-9 w-72"
                value={motivo}
                placeholder="Por que não é problema?"
                aria-label="Motivo da recusa"
                onChange={(event) => setMotivo(event.target.value)}
              />
              <Button
                type="submit"
                size="sm"
                variant="outline"
                loading={decidir.isPending}
                disabled={motivo.trim().length < 3}
              >
                Registrar recusa
              </Button>
              <span className="text-[0.68rem] text-slate-500">
                Recusa exige motivo: sem ele, ninguém aprende nada da recusa.
              </span>
            </form>
          )}
        </div>
      )}
    </div>
  )
}

function DetectorCard({ detector }: { detector: ImprovementDetector }) {
  const queryClient = useQueryClient()
  const visual = detector.last_status ? DETECTOR_STATUS[detector.last_status] : null
  const Icon = visual?.icon

  const salvar = useMutation({
    mutationFn: (input: { is_enabled?: boolean; config?: Record<string, number> }) =>
      improvementsApi.setDetector(detector.key, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'improvements'] })
      toast.success('Detector atualizado.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  return (
    <div
      className={`rounded-lg border p-3 ${
        detector.is_enabled ? 'border-border' : 'border-dashed border-border/60'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-white">
            {detector.label}
            {!detector.is_enabled && <Badge variant="outline">desligado</Badge>}
            {visual && Icon && (
              <span className={`flex items-center gap-1 text-xs ${visual.tone}`}>
                <Icon className="size-3.5" aria-hidden />
                {visual.label}
              </span>
            )}
          </p>
          <p className="mt-0.5 text-xs text-muted">{detector.description}</p>
          {/* O alcance declarado: sem ele, "não achou nada" vira garantia que o
              detector não deu. */}
          <p className="mt-1 text-[0.68rem] text-slate-500">Alcance: {detector.scope}</p>
          {detector.last_detail && (
            <p className={`mt-1 text-[0.68rem] ${visual?.tone ?? 'text-slate-500'}`}>
              Última passada: {detector.last_detail}
            </p>
          )}
        </div>
        <Toggle
          checked={detector.is_enabled}
          disabled={salvar.isPending}
          label={`Ligar o detector ${detector.label}`}
          onChange={(valor) => salvar.mutate({ is_enabled: valor })}
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-3">
        {Object.entries(detector.config).map(([chave, valor]) => (
          <label key={chave} className="text-[0.68rem] text-slate-500">
            {chave}
            <Input
              className="mt-1 h-9 w-28"
              type="number"
              min={0}
              defaultValue={valor}
              aria-label={`${chave} do detector ${detector.label}`}
              onBlur={(event) => {
                const novo = Number(event.target.value)
                if (!Number.isFinite(novo) || novo === valor) return
                salvar.mutate({ config: { [chave]: novo } })
              }}
            />
          </label>
        ))}
      </div>
    </div>
  )
}

/** Achados do analista, com os detectores e o que cada um conseguiu ver. */
export function ImprovementsSection() {
  const queryClient = useQueryClient()
  const [filtro, setFiltro] = useState('OPEN')
  const [relatorio, setRelatorio] = useState<ImprovementRun | null>(null)

  const detectores = useQuery({
    queryKey: queryKeys.improvementDetectors,
    queryFn: improvementsApi.detectors,
  })
  const achados = useQuery({
    queryKey: queryKeys.improvementFindings(filtro),
    queryFn: () => improvementsApi.findings({ status: filtro || undefined }),
  })

  const varrer = useMutation({
    mutationFn: () => improvementsApi.run(),
    onSuccess: (data) => {
      setRelatorio(data)
      queryClient.invalidateQueries({ queryKey: ['admin', 'improvements'] })
      toast.success(`${data.opened} achado(s) novo(s).`)
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'A varredura falhou.'),
  })

  const semAmostra = (relatorio?.detectors ?? []).filter(
    (item) => item.status === 'NOT_ENOUGH_DATA',
  )

  return (
    <div className="space-y-6">
      <Alert tone="info" title="O analista propõe. Quem decide e corrige é você.">
        Os detectores são determinísticos: olham os registros que a plataforma já tem e não
        chamam IA nenhuma. O analista <strong>não aplica mudança</strong>, não mexe em
        configuração — nem na que ele mesmo sugere — e <strong>não lê o repositório</strong>: a
        proposta vem em texto. Um achado só fecha quando o detector deixa de achá-lo.
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>Varredura</CardTitle>
          <CardDescription>
            Roda os detectores ligados e reconcilia os achados: o que voltou é atualizado, o que
            deixou de aparecer é fechado e o que reapareceu é reaberto.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" loading={varrer.isPending} onClick={() => varrer.mutate()}>
              <Play /> Rodar agora
            </Button>
            {relatorio && <IsolationBadge isolation={relatorio.isolation} />}
          </div>

          {relatorio && (
            <>
              <p className="text-xs text-muted">
                {relatorio.opened} novo(s) · {relatorio.updated} atualizado(s) ·{' '}
                {relatorio.resolved} fechado(s) · {relatorio.reopened} reaberto(s) ·{' '}
                {relatorio.muted} em recusa vigente
              </p>
              {semAmostra.length > 0 && (
                <Alert tone="warning" title="Detector sem amostra não fecha nada">
                  {semAmostra.map((item) => item.label).join(', ')} não{' '}
                  {semAmostra.length === 1 ? 'rodou' : 'rodaram'} nesta passada. Achado antigo
                  desses detectores continua aberto: ausência de medição não é ausência de
                  problema.
                </Alert>
              )}
              <ul className="space-y-1">
                {relatorio.detectors.map((item) => {
                  const visual = DETECTOR_STATUS[item.status]
                  const Icon = visual.icon
                  return (
                    <li key={item.key} className="flex items-start gap-2 text-xs">
                      <Icon className={`mt-0.5 size-3.5 shrink-0 ${visual.tone}`} aria-hidden />
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
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Achados</CardTitle>
          <CardDescription>
            Cada um traz os números que o produziram. Aceitar registra que vai ser feito; recusar
            exige motivo e silencia aquele achado pelo prazo configurado no detector.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="text-xs text-muted">
            Situação
            <Select
              className="mt-1 w-56"
              value={filtro}
              aria-label="Filtrar achados por situação"
              onChange={(event) => setFiltro(event.target.value)}
            >
              <option value="OPEN">abertos</option>
              <option value="ACCEPTED">aceitos</option>
              <option value="REJECTED">recusados</option>
              <option value="RESOLVED">fechados pelo detector</option>
              <option value="">todos</option>
            </Select>
          </label>

          {achados.isLoading && <SkeletonList rows={2} />}
          {achados.isError && (
            <ErrorState error={achados.error} onRetry={() => achados.refetch()} />
          )}
          {achados.data?.length === 0 && (
            <EmptyState
              icon={Lightbulb}
              title="Nenhum achado nesta situação"
              description="Rode a varredura para o analista olhar os registros da plataforma. Detector sem amostra vai dizer o que falta."
            />
          )}
          {achados.data?.map((item) => <FindingCard key={item.public_id} finding={item} />)}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Detectores</CardTitle>
          <CardDescription>
            Os limiares vivem no banco: mudar um é salvar aqui, não publicar versão.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {detectores.isLoading && <SkeletonList rows={3} />}
          {detectores.isError && (
            <ErrorState error={detectores.error} onRetry={() => detectores.refetch()} />
          )}
          {detectores.data?.map((item) => <DetectorCard key={item.key} detector={item} />)}
        </CardContent>
      </Card>
    </div>
  )
}

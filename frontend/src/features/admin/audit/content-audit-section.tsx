/**
 * O portão de qualidade na tela.
 *
 * Duas coisas esta tela não pode deixar passar:
 *
 * 1. **`NOT_CHECKED` não é verde.** O que o auditor não conseguiu conferir
 *    aparece com ícone e cor próprios, nunca somado ao que passou. Laudo limpo
 *    que escondeu a lacuna vira aprovação que ninguém deu.
 * 2. **A regra desligada fica à vista.** Desligar uma regra é a saída honesta
 *    quando ela está errada — mas tem que doer de ver, não sumir.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, CircleHelp, ShieldCheck, TriangleAlert } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/feedback/empty-state'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { Toggle } from '@/components/ui/toggle'
import { ApiError } from '@/lib/api/client'
import { contentAuditApi } from '@/lib/api/content-audit'
import { queryKeys } from '@/lib/query-client'
import type { AuditRule, AuditSeverity, AuditVerdict, ContentAudit } from '@/lib/api/types'

/**
 * Classes literais: o Tailwind 4 só emite a cor que **vê escrita no código**.
 * `text-${x}` montado em tempo de execução sai sem cor — já aconteceu três
 * vezes neste projeto.
 */
const SEVERITY: Record<AuditSeverity, { label: string; icon: LucideIcon; tone: string }> = {
  BLOCKER: { label: 'Bloqueia', icon: Ban, tone: 'text-danger' },
  WARNING: { label: 'Aviso', icon: TriangleAlert, tone: 'text-game-orange' },
  NOT_CHECKED: { label: 'Não conferido', icon: CircleHelp, tone: 'text-game-cyan' },
}

const VERDICT: Record<
  AuditVerdict,
  { label: string; variant: 'success' | 'warning' | 'danger' }
> = {
  CLEAN: { label: 'Limpo', variant: 'success' },
  WARNED: { label: 'Com aviso', variant: 'warning' },
  BLOCKED: { label: 'Bloqueado', variant: 'danger' },
}

const KIND_LABEL: Record<string, string> = {
  QUESTION: 'Questão',
  TRAINING_LESSON: 'Aula',
  MIND_MAP: 'Mapa mental',
  FLASHCARD_DECK: 'Baralho oficial',
}

const TRIGGER_LABEL: Record<string, string> = {
  PUBLISH: 'tentativa de publicação',
  MANUAL: 'conferência manual',
  AGENT: 'varredura do auditor',
}

function RuleRow({ rule }: { rule: AuditRule }) {
  const queryClient = useQueryClient()
  const salvar = useMutation({
    mutationFn: (input: { is_enabled: boolean; severity: string }) =>
      contentAuditApi.saveRule(rule.key, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auditRules })
      toast.success('Regra atualizada.')
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível salvar a regra.',
      ),
  })

  const mudou = rule.severity !== rule.default_severity
  const limiares = Object.entries(rule.config)

  return (
    <div
      className={`rounded-lg border p-3 ${
        rule.is_enabled ? 'border-border' : 'border-dashed border-danger/50 bg-danger-soft/20'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-white">
            {rule.label}
            {!rule.is_enabled && <Badge variant="danger">desligada</Badge>}
            {mudou && rule.is_enabled && (
              <Badge variant="outline">
                padrão:{' '}
                {SEVERITY[rule.default_severity as AuditSeverity]?.label ??
                  rule.default_severity}
              </Badge>
            )}
          </p>
          <p className="mt-0.5 text-xs text-muted">{rule.description}</p>
          <p className="mt-1 text-[0.68rem] text-slate-500">
            Vale para: {rule.applies_to.map((kind) => KIND_LABEL[kind] ?? kind).join(', ')}
            {limiares.length > 0 && (
              <>
                {' · '}
                {limiares.map(([chave, valor]) => `${chave}: ${valor}`).join(', ')}
              </>
            )}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Select
            className="h-9 w-36"
            value={rule.severity}
            disabled={!rule.is_enabled || salvar.isPending}
            onChange={(event) =>
              salvar.mutate({ is_enabled: rule.is_enabled, severity: event.target.value })
            }
          >
            <option value="BLOCKER">Bloqueia</option>
            <option value="WARNING">Só avisa</option>
          </Select>
          <Toggle
            checked={rule.is_enabled}
            disabled={salvar.isPending}
            label={`Ligar a regra ${rule.label}`}
            onChange={(valor) => salvar.mutate({ is_enabled: valor, severity: rule.severity })}
          />
        </div>
      </div>
    </div>
  )
}

function AuditCard({ audit }: { audit: ContentAudit }) {
  const veredito = VERDICT[audit.verdict]
  const naoConferidos = audit.findings.filter((item) => item.severity === 'NOT_CHECKED')

  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-white">
          {KIND_LABEL[audit.target_kind] ?? audit.target_kind}{' '}
          <span className="font-mono text-xs text-muted">{audit.target_public_id}</span>
        </p>
        <div className="flex items-center gap-2">
          {audit.blocked_publication && <Badge variant="danger">publicação barrada</Badge>}
          <Badge variant={veredito.variant}>{veredito.label}</Badge>
        </div>
      </div>
      <p className="mt-0.5 text-[0.68rem] text-slate-500">
        {TRIGGER_LABEL[audit.trigger] ?? audit.trigger} ·{' '}
        {new Date(audit.created_at).toLocaleString('pt-BR')}
      </p>

      <ul className="mt-2 space-y-1.5">
        {audit.findings.map((finding, index) => {
          const visual = SEVERITY[finding.severity]
          const Icon = visual.icon
          return (
            <li key={`${finding.rule}-${index}`} className="flex items-start gap-2">
              <Icon className={`mt-0.5 size-3.5 shrink-0 ${visual.tone}`} aria-hidden />
              <span className="text-xs text-slate-300">
                <span className={`font-semibold ${visual.tone}`}>{visual.label}:</span>{' '}
                {finding.message}
              </span>
            </li>
          )
        })}
      </ul>

      <p className="mt-2 text-[0.68rem] text-muted">
        {/* O alcance declarado: sem ele, "nada encontrado" é garantia que o auditor não deu. */}
        {typeof audit.summary.compared_questions === 'number' && (
          <>Comparado com {audit.summary.compared_questions} questões da disciplina. </>
        )}
        {naoConferidos.length > 0 && (
          <strong className="text-game-cyan">
            {naoConferidos.length} item(ns) não puderam ser conferidos.
          </strong>
        )}
      </p>
    </div>
  )
}

export function ContentAuditSection() {
  const [kind, setKind] = useState('')

  const rules = useQuery({ queryKey: queryKeys.auditRules, queryFn: contentAuditApi.rules })
  const params = { page: 1, page_size: 20, target_kind: kind || undefined }
  const audits = useQuery({
    queryKey: queryKeys.audits(params),
    queryFn: () => contentAuditApi.audits(params),
  })

  const desligadas = (rules.data ?? []).filter((rule) => !rule.is_enabled)

  return (
    <div className="space-y-6">
      <Alert tone="info" title="O auditor não usa IA, e diz o que não conseguiu conferir">
        As regras são determinísticas: a mesma questão recebe sempre o mesmo veredito, e a conta
        aparece. O que faltou insumo para julgar — tópico sem edital analisado, por exemplo —
        vira <strong>não conferido</strong>, nunca aprovação silenciosa.
      </Alert>

      {desligadas.length > 0 && (
        <Alert tone="warning" title="Há regra desligada">
          {desligadas.map((rule) => rule.label).join(', ')}. Conteúdo com esse defeito passa a
          publicar normalmente.
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck /> Regras do portão
          </CardTitle>
          <CardDescription>
            Severidade e limiar vivem aqui, não no código. Bloqueia impede a publicação; só
            avisa deixa passar com a marca no laudo.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {rules.isLoading && <SkeletonList rows={4} />}
          {(rules.data ?? []).map((rule) => (
            <RuleRow key={rule.key} rule={rule} />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Laudos</CardTitle>
              <CardDescription>
                Cada conferência é uma linha nova — o histórico mostra o defeito sumindo.
              </CardDescription>
            </div>
            <Select
              className="h-9 w-48"
              value={kind}
              onChange={(event) => setKind(event.target.value)}
            >
              <option value="">Todo tipo de conteúdo</option>
              <option value="QUESTION">Questões</option>
              <option value="TRAINING_LESSON">Aulas</option>
              <option value="MIND_MAP">Mapas mentais</option>
              <option value="FLASHCARD_DECK">Baralhos oficiais</option>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {audits.isLoading && <SkeletonList rows={3} />}
          {audits.data?.items.length === 0 && (
            <EmptyState
              icon={ShieldCheck}
              title="Nenhum laudo ainda"
              description="O portão grava um laudo a cada publicação conferida."
            />
          )}
          {(audits.data?.items ?? []).map((audit) => (
            <AuditCard key={audit.public_id} audit={audit} />
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

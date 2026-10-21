/**
 * Retificação de edital: o que mudou entre duas versões.
 *
 * Duas coisas esta tela não pode deixar passar:
 *
 * 1. **Conteúdo órfão não é conteúdo apagado.** Quando um tópico sai do edital,
 *    a aula continua existindo — a tela diz que ela ficou sem programa e deixa
 *    a decisão para uma pessoa. Não há botão de apagar aqui de propósito.
 * 2. **Dado deduzido não se parece com dado conferido.** Uma data que a IA
 *    inferiu do PDF recebe marca própria; tratá-la como oficial seria repassar
 *    como certo algo que ninguém conferiu.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, FileDiff, Minus, Plus, TriangleAlert, Unlink } from 'lucide-react'
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
import { noticeDiffApi } from '@/lib/api/notice-diff'
import { queryKeys } from '@/lib/query-client'
import type { NoticeChangeKind, NoticeDiff } from '@/lib/api/types'

/** Classes literais: o Tailwind 4 só emite a cor que vê escrita no código. */
const KIND: Record<NoticeChangeKind, { label: string; icon: LucideIcon; tone: string }> = {
  ADDED: { label: 'Entrou', icon: Plus, tone: 'text-success' },
  REMOVED: { label: 'Saiu', icon: Minus, tone: 'text-danger' },
  CHANGED: { label: 'Mudou', icon: ArrowRight, tone: 'text-game-gold' },
}

const SCOPE_LABEL: Record<string, string> = {
  SUBJECT: 'Disciplina',
  TOPIC: 'Tópico',
  EVENT: 'Data',
  FACT: 'Dado do edital',
}

const CONTENT_LABEL: Record<string, string> = {
  TRAINING_LESSON: 'Aula',
  MIND_MAP: 'Mapa mental',
}

/** Plural certo: texto torto tira a confiança do que o número diz. */
function plural(quantos: number, singular: string, plural_: string): string {
  return `${quantos} ${quantos === 1 ? singular : plural_}`
}

/** Conferido no documento é diferente de deduzido — e a tela mostra isso. */
function Evidencia({ nivel }: { nivel: string | null }) {
  if (!nivel) return null
  if (nivel === 'OFFICIAL' || nivel === 'CONFIRMED') {
    return <Badge variant="success">conferido no edital</Badge>
  }
  if (nivel === 'INFERRED') return <Badge variant="warning">deduzido pela IA</Badge>
  return <Badge variant="outline">não localizado</Badge>
}

function DiffCard({ diff }: { diff: NoticeDiff }) {
  const queryClient = useQueryClient()
  const marcar = useMutation({
    mutationFn: () => noticeDiffApi.markReviewed(diff.public_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'notice-diffs'] })
      toast.success('Marcada como lida.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível marcar.'),
  })

  const orfaos = diff.impacts.filter((item) => item.action === 'ORPHANED')
  const faltando = diff.impacts.filter((item) => item.action === 'MISSING')

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-base">
              {diff.from_notice_title} <ArrowRight className="inline size-4" />{' '}
              {diff.to_notice_title}
            </CardTitle>
            <CardDescription>
              {plural(diff.summary.added ?? 0, 'entrou', 'entraram')} ·{' '}
              {plural(diff.summary.removed ?? 0, 'saiu', 'saíram')} ·{' '}
              {plural(diff.summary.changed ?? 0, 'mudou', 'mudaram')} ·{' '}
              {new Date(diff.created_at).toLocaleDateString('pt-BR')}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {diff.reviewed_at ? (
              <Badge variant="success">lida</Badge>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => marcar.mutate()}>
                Marcar como lida
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {(diff.summary.inferred ?? 0) > 0 && (
          <Alert tone="warning" title="Parte do que mudou foi deduzido, não conferido">
            {plural(diff.summary.inferred ?? 0, 'mudança veio', 'mudanças vieram')} de dado que
            a IA deduziu do documento. Confira no PDF antes de repassar como oficial.
          </Alert>
        )}

        {orfaos.length > 0 && (
          <Alert
            tone="warning"
            title={`${orfaos.length} conteúdo(s) sem programa que os cobre`}
          >
            O tópico saiu do edital. <strong>Nada foi apagado</strong> — o que fazer com cada um
            é decisão de uma pessoa.
          </Alert>
        )}

        {diff.changes.length === 0 && (
          <p className="text-sm text-muted">
            As duas versões analisadas não têm diferença no que a plataforma compara.
          </p>
        )}

        <ul className="space-y-1.5">
          {diff.changes.map((change, index) => {
            const visual = KIND[change.kind]
            const Icon = visual.icon
            return (
              <li
                key={`${change.scope}-${change.label}-${index}`}
                className="flex items-start gap-2 rounded-md border border-border p-2"
              >
                <Icon className={`mt-0.5 size-3.5 shrink-0 ${visual.tone}`} aria-hidden />
                <span className="min-w-0 flex-1 text-xs">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-white">{change.label}</span>
                    <span className="text-muted">
                      {SCOPE_LABEL[change.scope] ?? change.scope}
                    </span>
                    <span className={`font-medium ${visual.tone}`}>{visual.label}</span>
                    <Evidencia nivel={change.evidence_level} />
                  </span>
                  {(change.before || change.after) && (
                    <span className="mt-0.5 block text-slate-300">
                      {change.before && <s className="text-muted">{change.before}</s>}
                      {change.before && change.after && ' → '}
                      {change.after}
                    </span>
                  )}
                  <span className="block text-slate-400">{change.detail}</span>
                </span>
              </li>
            )
          })}
        </ul>

        {orfaos.length > 0 && (
          <div className="space-y-1.5">
            <p className="game-label text-[0.6rem] text-muted">Conteúdo sem programa</p>
            {orfaos.map((item, index) => (
              <div
                key={`${item.topic_label}-${index}`}
                className="flex items-start gap-2 rounded-md border border-dashed border-danger/50 p-2"
              >
                <Unlink className="mt-0.5 size-3.5 shrink-0 text-danger" aria-hidden />
                <span className="text-xs">
                  <span className="font-semibold text-white">
                    {item.content ? item.content.title : item.topic_label}
                  </span>{' '}
                  <span className="text-muted">
                    (
                    {item.content
                      ? (CONTENT_LABEL[item.content.kind] ?? item.content.kind)
                      : '—'}{' '}
                    · tópico {item.topic_label})
                  </span>
                  <span className="block text-slate-400">{item.reason}</span>
                </span>
              </div>
            ))}
          </div>
        )}

        {faltando.length > 0 && (
          <div className="space-y-1.5">
            <p className="game-label text-[0.6rem] text-muted">Tópicos novos sem conteúdo</p>
            {faltando.map((item, index) => (
              <div
                key={`${item.topic_label}-${index}`}
                className="flex items-start gap-2 rounded-md border border-border p-2"
              >
                <TriangleAlert
                  className="mt-0.5 size-3.5 shrink-0 text-game-orange"
                  aria-hidden
                />
                <span className="text-xs">
                  <span className="font-semibold text-white">{item.topic_label}</span>
                  <span className="block text-slate-400">{item.reason}</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function NoticeDiffSection() {
  const queryClient = useQueryClient()
  const [competition, setCompetition] = useState('')

  const params = { page: 1, page_size: 10 }
  const diffs = useQuery({
    queryKey: queryKeys.noticeDiffs(params),
    queryFn: () => noticeDiffApi.list(params),
  })
  const competitions = useQuery({
    queryKey: ['admin', 'catalog', 'competitions', 'for-diff'],
    queryFn: () => adminCatalogApi.competitions({ page: 1, page_size: 50 }),
  })

  const comparar = useMutation({
    mutationFn: () => noticeDiffApi.compare(competition),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'notice-diffs'] })
      toast.success('Comparação pronta.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível comparar.'),
  })

  return (
    <div className="space-y-6">
      <Alert tone="info" title="Comparar não muda nada">
        A comparação é entre duas análises que já existem — sem IA, sem reescrever edital. O que
        ela produz é o registro do que mudou e do que isso atinge:{' '}
        <strong>conteúdo de tópico que saiu fica órfão, nunca apagado</strong>.
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileDiff /> Comparar versões
          </CardTitle>
          <CardDescription>
            Compara as duas versões analisadas mais recentes do concurso.
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
          <Button
            onClick={() => comparar.mutate()}
            disabled={!competition || comparar.isPending}
          >
            Comparar
          </Button>
        </CardContent>
      </Card>

      {diffs.isLoading && <SkeletonList rows={2} />}
      {diffs.data?.items.length === 0 && (
        <EmptyState
          icon={FileDiff}
          title="Nenhuma comparação ainda"
          description="Escolha um concurso com duas versões de edital analisadas."
        />
      )}
      {(diffs.data?.items ?? []).map((diff) => (
        <DiffCard key={diff.public_id} diff={diff} />
      ))}
    </div>
  )
}

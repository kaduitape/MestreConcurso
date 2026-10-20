/**
 * Vínculo de conteúdo com o catálogo.
 *
 * A tela existe por causa de uma regra: a sugestão **não aplica nada**. O
 * casamento entre o texto livre da aula e o catálogo é calculado sem IA, vem
 * ordenado e com o motivo da nota — mas quem confirma é a pessoa que está
 * olhando. Casar no chute mandaria a aula para o tópico errado, e o aluno
 * estudaria achando que está no lugar certo.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link2, Link2Off, Map as MapIcon, Theater } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/feedback/empty-state'
import { SkeletonList } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import { catalogLinkApi } from '@/lib/api/catalog-link'
import { queryKeys } from '@/lib/query-client'
import type { CatalogMatchCandidate, LinkableKind, PendingLink } from '@/lib/api/types'

const KIND_LABEL: Record<LinkableKind, string> = {
  TRAINING: 'Aula',
  MINDMAP: 'Mapa mental',
}

const selectClass =
  'h-9 w-full rounded-md border border-border bg-surface px-2 text-sm text-foreground shadow-xs transition focus:border-primary focus:outline-2 focus:outline-offset-1 focus:outline-primary'

function Candidate({ item }: { item: CatalogMatchCandidate }) {
  return (
    <span className="flex items-center gap-1.5">
      {item.name}
      <span className="text-[0.68rem] text-muted">
        {Math.round(item.score * 100)}% · {item.reason_label}
      </span>
    </span>
  )
}

function PendingRow({ item }: { item: PendingLink }) {
  const queryClient = useQueryClient()
  const [subject, setSubject] = useState(item.subject_public_id ?? '')
  const [topic, setTopic] = useState('')

  const topics = useQuery({
    queryKey: queryKeys.linkTopics(item.kind, item.public_id, subject),
    queryFn: () => catalogLinkApi.topics(item.kind, item.public_id, subject),
    enabled: Boolean(subject),
  })

  const save = useMutation({
    mutationFn: () =>
      catalogLinkApi.link(item.kind, item.public_id, {
        subject_public_id: subject || null,
        topic_public_id: topic || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'catalog', 'links'] })
      toast.success('Vínculo gravado.')
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível gravar o vínculo.',
      ),
  })

  const Icon = item.kind === 'TRAINING' ? Theater : MapIcon
  const sugeridas = item.subject_suggestions.candidates

  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-semibold text-white">
            <Icon className="size-4 shrink-0 text-muted" aria-hidden />
            <span className="truncate">{item.title}</span>
          </p>
          <p className="mt-1 text-xs text-muted">
            {KIND_LABEL[item.kind]} · escrito como “{item.subject_text} / {item.topic_text}”
          </p>
        </div>
        <Badge variant={item.subject_public_id ? 'warning' : 'neutral'}>
          {item.subject_public_id ? 'falta o tópico' : 'sem vínculo'}
        </Badge>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
        <label className="block">
          <span className="game-label mb-1 block text-[0.6rem] text-muted">Disciplina</span>
          <select
            className={selectClass}
            value={subject}
            aria-label={`Disciplina de ${item.title}`}
            onChange={(event) => {
              setSubject(event.target.value)
              setTopic('')
            }}
          >
            <option value="">— nenhuma —</option>
            {sugeridas.map((candidate) => (
              <option key={candidate.public_id} value={candidate.public_id}>
                {candidate.name} ({Math.round(candidate.score * 100)}%)
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="game-label mb-1 block text-[0.6rem] text-muted">Tópico</span>
          <select
            className={selectClass}
            value={topic}
            disabled={!subject || topics.isLoading}
            aria-label={`Tópico de ${item.title}`}
            onChange={(event) => setTopic(event.target.value)}
          >
            <option value="">— nenhum —</option>
            {(topics.data?.candidates ?? []).map((candidate) => (
              <option key={candidate.public_id} value={candidate.public_id}>
                {candidate.name} ({Math.round(candidate.score * 100)}%)
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-end">
          <Button onClick={() => save.mutate()} disabled={save.isPending}>
            {subject ? <Link2 className="size-4" /> : <Link2Off className="size-4" />}
            {subject ? 'Vincular' : 'Deixar sem vínculo'}
          </Button>
        </div>
      </div>

      {sugeridas.length === 0 && (
        // Lista vazia é resposta: o catálogo não tem essa disciplina.
        <p className="mt-2 text-xs text-muted">
          Nenhuma disciplina do catálogo se parece com “{item.subject_text}”. Cadastre a
          disciplina antes de vincular.
        </p>
      )}
      {sugeridas.length > 0 && (
        <p className="mt-2 text-xs text-muted">
          Sugestão: <Candidate item={sugeridas[0]} />
        </p>
      )}
    </div>
  )
}

export function CatalogLinksSection() {
  const params = { page: 1, page_size: 50 }
  const pending = useQuery({
    queryKey: queryKeys.pendingLinks(params),
    queryFn: () => catalogLinkApi.pending(params),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link2 /> Vínculo com o catálogo
        </CardTitle>
        <CardDescription>
          Aulas e mapas mentais que ainda não sabem de qual tópico são.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert tone="info" title="A sugestão não decide">
          A nota é calculada comparando os nomes — sem IA, mesma entrada sempre dá a mesma
          saída. Confirme olhando: vincular ao tópico errado faz o aluno estudar a coisa errada
          achando que está no lugar certo.
        </Alert>

        {pending.isLoading && <SkeletonList rows={3} />}
        {pending.data?.items.length === 0 && (
          <EmptyState
            icon={Link2}
            title="Tudo vinculado"
            description="Nenhuma aula ou mapa mental esperando vínculo."
          />
        )}
        {pending.data?.items.map((item) => (
          <PendingRow key={`${item.kind}-${item.public_id}`} item={item} />
        ))}
      </CardContent>
    </Card>
  )
}

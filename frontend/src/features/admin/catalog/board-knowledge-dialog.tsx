import { useQuery } from '@tanstack/react-query'
import { Brain } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { adminCatalogApi } from '@/lib/api/catalog'
import type { BoardKnowledgeEntry, ExamBoard } from '@/lib/api/types'

const SOURCE_LABEL: Record<BoardKnowledgeEntry['source'], { label: string; tone: string }> = {
  COMPUTED: { label: 'Calculado', tone: 'info' },
  AI: { label: 'Gerado por IA', tone: 'primary' },
  EDITORIAL: { label: 'Curadoria', tone: 'neutral' },
  OFFICIAL: { label: 'Oficial', tone: 'success' },
}

function sampleLabel(entry: BoardKnowledgeEntry): string {
  const parts: string[] = []
  if (entry.sample_exams) parts.push(`${entry.sample_exams} provas`)
  if (entry.sample_questions) parts.push(`${entry.sample_questions} questões`)
  if (entry.period_start_year && entry.period_end_year) {
    parts.push(`${entry.period_start_year}–${entry.period_end_year}`)
  }
  return parts.join(' · ')
}

/**
 * Mostra o que já está gravado sobre a banca. É esta base que evita chamar a IA
 * de novo: enquanto houver registro válido, a plataforma lê daqui.
 */
export function BoardKnowledgeDialog({
  board,
  onClose,
}: {
  board: ExamBoard | null
  onClose: () => void
}) {
  const entries = useQuery({
    queryKey: ['admin', 'catalog', 'board-knowledge', board?.public_id],
    queryFn: () => adminCatalogApi.boardKnowledge(board!.public_id),
    enabled: Boolean(board),
  })

  const coverage = useQuery({
    queryKey: ['admin', 'catalog', 'board-knowledge-coverage', board?.public_id],
    queryFn: () => adminCatalogApi.boardKnowledgeCoverage(board!.public_id),
    enabled: Boolean(board),
  })

  return (
    <Dialog open={Boolean(board)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Conhecimento sobre {board?.short_name}</DialogTitle>
          <DialogDescription>
            Tudo o que a plataforma já apurou fica guardado aqui, com origem e amostra. Nada é
            recalculado — nem repago — enquanto o registro estiver válido.
          </DialogDescription>
        </DialogHeader>

        {coverage.data && (
          <div className="mb-4 grid grid-cols-3 gap-3 rounded-md bg-surface-muted p-3 text-center">
            <div>
              <p className="text-xs text-subtle uppercase">Registros</p>
              <p className="text-xl font-semibold">{coverage.data.total}</p>
            </div>
            <div>
              <p className="text-xs text-subtle uppercase">Vencidos</p>
              <p className="text-xl font-semibold">{coverage.data.expired}</p>
            </div>
            <div>
              <p className="text-xs text-subtle uppercase">Tokens guardados</p>
              <p className="text-xl font-semibold">
                {coverage.data.ai_tokens_stored.toLocaleString('pt-BR')}
              </p>
            </div>
          </div>
        )}

        {entries.isLoading && <SkeletonList rows={2} />}

        {entries.data?.length === 0 && (
          <EmptyState
            icon={Brain}
            title="Nada apurado ainda"
            description="Quando a análise de banca entrar no ar (Fase 6), cada resultado será gravado aqui automaticamente."
          />
        )}

        <ul className="max-h-96 space-y-3 overflow-y-auto">
          {entries.data?.map((entry) => (
            <li key={entry.id} className="rounded-md border border-border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium">{entry.title}</p>
                <Badge
                  variant={
                    SOURCE_LABEL[entry.source].tone as
                      'info' | 'primary' | 'neutral' | 'success'
                  }
                >
                  {SOURCE_LABEL[entry.source].label}
                </Badge>
                {entry.is_expired && <Badge variant="warning">Vencido</Badge>}
              </div>
              {entry.content && <p className="mt-1 text-sm text-muted">{entry.content}</p>}
              <p className="mt-2 text-xs text-subtle">
                {sampleLabel(entry) || 'sem amostra registrada'}
                {entry.model_slug && ` · ${entry.model_slug}`}
                {entry.input_tokens + entry.output_tokens > 0 &&
                  ` · ${entry.input_tokens + entry.output_tokens} tokens (pagos uma única vez)`}
              </p>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  )
}

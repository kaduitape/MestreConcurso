import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/feedback/empty-state'
import { SkeletonList } from '@/components/ui/skeleton'
import { mindmapApi } from '@/lib/api/mindmap'
import { queryKeys } from '@/lib/query-client'
import { MindMapBoard } from './mindmap-board'

export function MindMapPage() {
  const { publicId = '' } = useParams()
  const map = useQuery({
    queryKey: queryKeys.mindmap(publicId),
    queryFn: () => mindmapApi.map(publicId),
    enabled: Boolean(publicId),
  })

  if (map.isLoading) return <SkeletonList rows={5} />
  if (!map.data) {
    return (
      <EmptyState
        icon={Sparkles}
        title="Mapa não encontrado"
        description="Ele pode ter sido despublicado enquanto você estudava."
      />
    )
  }

  return (
    <div className="space-y-4">
      <Link
        to="/mapas-mentais"
        className="inline-flex items-center gap-2 text-sm text-muted hover:text-white"
      >
        <ArrowLeft className="size-4" /> Todos os mapas
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="game-label text-game-gold">{map.data.subject}</p>
          <h1 className="mt-1 text-2xl font-extrabold text-white">{map.data.title}</h1>
        </div>
        {/* O rótulo é obrigatório: o mapa foi estruturado por IA e revisado por
            uma pessoa, e quem estuda tem o direito de saber disso. */}
        <Badge variant="warning">Gerado por IA · revisado</Badge>
      </div>

      <MindMapBoard content={map.data.content} />
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Map as MapIcon, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/feedback/empty-state'
import { SkeletonList } from '@/components/ui/skeleton'
import { mindmapApi } from '@/lib/api/mindmap'
import { queryKeys } from '@/lib/query-client'

export function MindMapLibraryPage() {
  const params = { page: 1, page_size: 30 }
  const maps = useQuery({
    queryKey: queryKeys.mindmaps(params),
    queryFn: () => mindmapApi.published(params),
  })

  return (
    <div className="space-y-6">
      <div>
        <p className="game-label text-game-gold">Memorização visual</p>
        <h1 className="mt-1 text-2xl font-extrabold text-white">Mapas mentais</h1>
        <p className="mt-2 text-sm text-slate-400">
          O assunto inteiro em uma tela: conceito, regras, exceções, macetes e as pegadinhas que
          a banca costuma usar.
        </p>
      </div>

      {maps.isLoading && <SkeletonList rows={4} />}
      {maps.data?.items.length === 0 && (
        <EmptyState
          icon={Sparkles}
          title="Nenhum mapa publicado"
          description="Assim que o estúdio publicar um mapa revisado, ele aparecerá aqui."
        />
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {maps.data?.items.map((item) => (
          <Card
            key={item.public_id}
            className="group border-game-gold/20 transition hover:-translate-y-0.5 hover:border-game-gold/45"
          >
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <Badge variant="warning">Mapa mental</Badge>
                <span className="text-xs text-muted">
                  {item.content.panels?.length ?? 0} painéis
                </span>
              </div>
              <CardTitle className="mt-3">{item.title}</CardTitle>
              <CardDescription>
                {item.subject} · {item.topic}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Link
                to={`/mapas-mentais/${item.public_id}`}
                className="inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline"
              >
                <MapIcon className="size-4" /> Abrir mapa
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

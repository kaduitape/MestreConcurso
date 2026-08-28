import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { SkeletonList } from '@/components/ui/skeleton'
import { api } from '@/lib/api/client'
import type { ShareCard } from '@/lib/api/types'
import { ShareCardPreview } from './components/share-card-preview'

/**
 * A página aberta do card. Não exige sessão: é o link que o candidato escolheu
 * compartilhar. Revogado o link, esta tela deixa de encontrar o card.
 */
export function PublicCardPage() {
  const { token = '' } = useParams()

  const card = useQuery({
    queryKey: ['public-card', token],
    queryFn: () => api.get<ShareCard>(`/game/cards/public/${token}`),
    retry: false,
  })

  return (
    <div className="mx-auto max-w-xl space-y-6 px-4 py-12">
      {card.isLoading && <SkeletonList rows={3} />}

      {card.isError && (
        <div className="rounded-lg border border-dashed border-border p-8 text-center">
          <p className="font-medium">Card não encontrado</p>
          <p className="mt-1 text-sm text-muted">
            O link pode ter sido revogado por quem o publicou.
          </p>
        </div>
      )}

      {card.data && (
        <>
          <ShareCardPreview card={card.data} />
          <p className="text-center text-xs text-subtle">
            Concurso Mestre IA — preparação medida por dados reais.
          </p>
        </>
      )}
    </div>
  )
}

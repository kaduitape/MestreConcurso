/**
 * Baralhos oficiais: o que a equipe publicou para os tópicos do meu edital.
 *
 * A tela existe por causa de uma regra de escopo: cartão oficial **não** entra
 * na fila de ninguém por decisão da plataforma. O candidato entra no baralho, e
 * é esse consentimento que faz os cartões aparecerem na revisão — respeitando o
 * teto de cartões novos por dia, como qualquer cartão.
 *
 * Sair do baralho tira os cartões da fila e **não apaga** o histórico de
 * revisão: quem volta meses depois reencontra os intervalos onde parou.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpenCheck, LogIn, LogOut } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { decksApi } from '@/lib/api/decks'
import { queryKeys } from '@/lib/query-client'
import type { OfficialDeck } from '@/lib/api/types'

function DeckCard({ deck }: { deck: OfficialDeck }) {
  const queryClient = useQueryClient()

  const alternar = useMutation({
    mutationFn: () =>
      deck.is_subscribed
        ? decksApi.unsubscribe(deck.public_id)
        : decksApi.subscribe(deck.public_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.officialDecks })
      queryClient.invalidateQueries({ queryKey: ['review'] })
      queryClient.invalidateQueries({ queryKey: ['flashcards'] })
      toast.success(
        deck.is_subscribed
          ? 'Você saiu do baralho. Seu histórico de revisão continua guardado.'
          : 'Pronto. Os cartões entram na sua fila respeitando o teto de novos por dia.',
      )
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível concluir.'),
  })

  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-white">{deck.title}</p>
          <p className="mt-0.5 text-[0.68rem] text-subtle">
            {deck.subject_name ?? 'sem disciplina'} · {deck.active_cards} cartão(ões)
            {deck.ai_cards > 0 && ` · ${deck.ai_cards} gerado(s) por IA`}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Badge variant="success">oficial</Badge>
          {deck.ai_cards > 0 && <Badge variant="info">tem cartão gerado por IA</Badge>}
        </div>
      </div>

      {deck.description && <p className="mt-2 text-xs text-slate-300">{deck.description}</p>}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant={deck.is_subscribed ? 'outline' : 'primary'}
          loading={alternar.isPending}
          onClick={() => alternar.mutate()}
        >
          {deck.is_subscribed ? <LogOut /> : <LogIn />}
          {deck.is_subscribed ? 'Sair do baralho' : 'Entrar no baralho'}
        </Button>
        {deck.is_subscribed && (
          <span className="text-[0.68rem] text-subtle">
            Os cartões deste baralho estão na sua fila de revisão.
          </span>
        )}
      </div>
    </div>
  )
}

export function OfficialDecksPage() {
  const catalogo = useQuery({
    queryKey: queryKeys.officialDecks,
    queryFn: () => decksApi.catalogue(),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Baralhos oficiais"
        description="Cartões curados pela equipe para os tópicos do seu edital. Você escolhe em quais entrar."
      />

      {catalogo.isPending && <SkeletonList rows={4} />}
      {catalogo.isError && <ErrorState error={catalogo.error} onRetry={() => catalogo.refetch()} />}

      {catalogo.data && (
        <Card>
          <CardContent className="space-y-4 pt-6">
            <Alert tone="info">{catalogo.data.scope}</Alert>
            {catalogo.data.items.length === 0 ? (
              <EmptyState
                icon={BookOpenCheck}
                title="Nenhum baralho publicado para os seus tópicos"
                description="Quando a equipe publicar um baralho de um tópico do seu edital, ele aparece aqui."
              />
            ) : (
              <div className="space-y-2">
                {catalogo.data.items.map((deck) => (
                  <DeckCard key={deck.public_id} deck={deck} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

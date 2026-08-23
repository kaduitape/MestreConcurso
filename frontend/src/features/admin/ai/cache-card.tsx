import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { aiApi } from '@/lib/api/ai'
import { queryKeys } from '@/lib/query-client'

function formatNumber(value: number): string {
  return value.toLocaleString('pt-BR')
}

export function CacheCard() {
  const queryClient = useQueryClient()
  const cache = useQuery({ queryKey: queryKeys.aiCache, queryFn: aiApi.cacheStats })

  const purge = useMutation({
    mutationFn: (expiredOnly: boolean) => aiApi.purgeCache(expiredOnly),
    onSuccess: (response) => {
      toast.success(response.message)
      queryClient.invalidateQueries({ queryKey: queryKeys.aiCache })
    },
  })

  const stats = cache.data

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="size-4 text-muted" aria-hidden /> Cache de respostas de IA
        </CardTitle>
        <CardDescription>
          Toda resposta é guardada por impressão digital da requisição. Perguntar de novo a
          mesma coisa não gasta tokens — os números abaixo vêm dos contadores reais de uso.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-4">
          {[
            ['Entradas guardadas', stats?.entries],
            ['Reaproveitamentos', stats?.total_hits],
            ['Tokens economizados', stats?.tokens_saved],
            ['Entradas vencidas', stats?.expired_entries],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-md bg-surface-muted p-3">
              <p className="text-xs tracking-wide text-subtle uppercase">{label}</p>
              {cache.isLoading ? (
                <Skeleton className="mt-1 h-7 w-16" />
              ) : (
                <p className="text-2xl font-semibold tabular-nums">
                  {formatNumber(Number(value ?? 0))}
                </p>
              )}
            </div>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            loading={purge.isPending}
            onClick={() => purge.mutate(true)}
          >
            <Trash2 /> Limpar apenas o vencido
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-danger"
            loading={purge.isPending}
            onClick={() => purge.mutate(false)}
          >
            Limpar tudo
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

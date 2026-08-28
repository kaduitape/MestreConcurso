import { useMutation } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError } from '@/lib/api/client'
import { intelligenceApi } from '@/lib/api/intelligence'

export function IntelligenceSection() {
  const recompute = useMutation({
    mutationFn: () => intelligenceApi.recomputeBoards(),
    onSuccess: (results) => {
      const rows = results.reduce((total, item) => total + item.incidence_rows, 0)
      toast.success(
        `${results.length} banca(s) processada(s), ${rows} recorte(s) publicado(s).`,
      )
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível recalcular.'),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Incidência e DNA das bancas</CardTitle>
        <CardDescription>
          Ambos são contagem sobre as questões cadastradas. O recálculo regrava os recortes com
          amostra suficiente e descarta os demais — nenhum percentual sobrevive sem base.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button loading={recompute.isPending} onClick={() => recompute.mutate()}>
          <RefreshCw /> Recalcular todas as bancas
        </Button>

        {recompute.data && (
          <ul className="space-y-2">
            {recompute.data.map((item) => (
              <li key={item.board_slug} className="rounded-md border border-border p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{item.board_slug}</span>
                  <Badge variant="outline">{item.questions_sampled} questões</Badge>
                  <Badge variant={item.incidence_rows > 0 ? 'success' : 'warning'}>
                    {item.incidence_rows} recorte(s) de incidência
                  </Badge>
                  <Badge variant={item.profile_metrics > 0 ? 'success' : 'warning'}>
                    {item.profile_metrics} métrica(s) de perfil
                  </Badge>
                </div>
                {item.incidence_blocked && (
                  <p className="mt-2 text-xs text-warning">{item.incidence_blocked}</p>
                )}
                {item.profile_blocked && (
                  <p className="mt-1 text-xs text-warning">{item.profile_blocked}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

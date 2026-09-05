import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SkeletonList } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import { battleSettingsApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'

/**
 * As réguas da Batalha RPG.
 *
 * Quando uma alternativa "fica longa" é uma decisão de produto, não uma
 * constante de código: o dia em que a arena começar a espremer texto em algum
 * aparelho, o número muda aqui e passa a valer na questão seguinte.
 */
export function BattleSettingsSection() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Record<string, number>>({})

  const settings = useQuery({
    queryKey: queryKeys.battleSettings,
    queryFn: () => battleSettingsApi.list(),
  })

  const update = useMutation({
    mutationFn: (input: { key: string; value: number }) =>
      battleSettingsApi.update(input.key, input.value),
    onSuccess: () => {
      toast.success('Régua atualizada. Vale a partir da próxima questão.')
      queryClient.invalidateQueries({ queryKey: queryKeys.battleSettings })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível atualizar.'),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Batalha RPG — réguas de layout</CardTitle>
        <CardDescription>
          Os limites que decidem entre a arena (monstro por alternativa) e o modo compacto
          (texto inteiro). A alteração vale sem deploy e fica registrada na auditoria.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {settings.isLoading && <SkeletonList rows={4} />}

        <ul className="space-y-2">
          {settings.data?.map((item) => {
            const local = draft[item.key] ?? item.value
            const dirty = local !== item.value

            return (
              <li
                key={item.key}
                className="flex flex-wrap items-center gap-3 rounded-md border border-border p-3 text-sm"
              >
                <span className="min-w-48 flex-1">
                  <span className="block font-medium">{item.label}</span>
                  <span className="text-xs text-subtle">{item.key}</span>
                </span>

                <Input
                  type="number"
                  min={1}
                  className="w-24"
                  aria-label={item.label}
                  value={local}
                  onChange={(event) =>
                    setDraft({ ...draft, [item.key]: Number(event.target.value) })
                  }
                />

                {dirty && (
                  <Button
                    size="sm"
                    loading={update.isPending}
                    onClick={() => update.mutate({ key: item.key, value: local })}
                  >
                    <Save /> Salvar
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

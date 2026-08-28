import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SkeletonList } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import { gameRulesApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'

export function GameRulesSection() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Record<string, { xp_value: number; daily_cap: number }>>(
    {},
  )

  const rules = useQuery({
    queryKey: queryKeys.gameRules,
    queryFn: () => gameRulesApi.list(),
  })

  const update = useMutation({
    mutationFn: (input: {
      key: string
      xp_value?: number
      daily_cap?: number
      is_enabled?: boolean
    }) => gameRulesApi.update(input.key, input),
    onSuccess: () => {
      toast.success('Regra atualizada. Vale a partir do próximo evento.')
      queryClient.invalidateQueries({ queryKey: queryKeys.gameRules })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível atualizar.'),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Regras de pontuação</CardTitle>
        <CardDescription>
          Valor, teto diário e liga/desliga por evento. A alteração vale sem deploy e fica
          registrada na auditoria.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {rules.isLoading && <SkeletonList rows={4} />}

        <ul className="space-y-2">
          {rules.data?.map((rule) => {
            const local = draft[rule.key] ?? {
              xp_value: rule.xp_value,
              daily_cap: rule.daily_cap,
            }
            const dirty = local.xp_value !== rule.xp_value || local.daily_cap !== rule.daily_cap

            return (
              <li
                key={rule.key}
                className="flex flex-wrap items-center gap-3 rounded-md border border-border p-3 text-sm"
              >
                <span className="min-w-48 flex-1">
                  <span className="block font-medium">{rule.label}</span>
                  <span className="text-xs text-subtle">{rule.key}</span>
                </span>

                <label className="flex items-center gap-2 text-xs">
                  XP
                  <Input
                    type="number"
                    min={0}
                    className="w-24"
                    aria-label={`XP de ${rule.label}`}
                    value={local.xp_value}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        [rule.key]: { ...local, xp_value: Number(event.target.value) },
                      })
                    }
                  />
                </label>

                <label className="flex items-center gap-2 text-xs">
                  Teto/dia
                  <Input
                    type="number"
                    min={0}
                    className="w-24"
                    aria-label={`Teto diário de ${rule.label}`}
                    value={local.daily_cap}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        [rule.key]: { ...local, daily_cap: Number(event.target.value) },
                      })
                    }
                  />
                </label>

                <Button
                  size="sm"
                  variant={rule.is_enabled ? 'outline' : 'ghost'}
                  onClick={() => update.mutate({ key: rule.key, is_enabled: !rule.is_enabled })}
                >
                  {rule.is_enabled ? 'Ativa' : 'Desativada'}
                </Button>

                {dirty && (
                  <Button
                    size="sm"
                    loading={update.isPending}
                    onClick={() =>
                      update.mutate({
                        key: rule.key,
                        xp_value: local.xp_value,
                        daily_cap: local.daily_cap,
                      })
                    }
                  >
                    <Save /> Salvar
                  </Button>
                )}

                {!rule.is_enabled && <Badge variant="warning">não pontua</Badge>}
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

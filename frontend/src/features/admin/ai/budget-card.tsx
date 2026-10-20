/**
 * Teto de gasto com IA.
 *
 * Duas coisas que a tela precisa deixar claras, porque são as que mais enganam
 * quem administra:
 *
 * 1. **Com o controle desligado, a medição continua.** É o que permite
 *    descobrir qual teto faz sentido antes de ligá-lo.
 * 2. **O total pode estar incompleto.** Modelo sem preço cadastrado grava os
 *    tokens mas não consegue virar dinheiro. Um número menor que o real é pior
 *    que nenhum número, então a tela diz quais modelos faltam cadastrar.
 */
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleDollarSign, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Toggle } from '@/components/ui/toggle'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import { aiApi } from '@/lib/api/ai'
import { queryKeys } from '@/lib/query-client'

/** Centavos (string decimal) para reais legíveis. */
function toReais(cents: string): string {
  const value = Number(cents) / 100
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

/** Mostra o limite em reais, ou avisa que zero quer dizer "sem teto". */
function describeLimit(cents: string): string {
  const value = Number(cents)
  if (!Number.isFinite(value)) return 'Valor inválido.'
  if (value <= 0) return 'Sem teto para este.'
  return `Equivale a ${toReais(cents)}.`
}

export function BudgetCard() {
  const queryClient = useQueryClient()
  const budget = useQuery({ queryKey: queryKeys.aiBudget, queryFn: aiApi.budget })

  const [enabled, setEnabled] = useState(false)
  const [monthly, setMonthly] = useState('0')
  const [perRun, setPerRun] = useState('0')

  useEffect(() => {
    if (budget.data) {
      setEnabled(budget.data.is_enabled)
      setMonthly(budget.data.monthly_limit_cents)
      setPerRun(budget.data.per_run_limit_cents)
    }
  }, [budget.data])

  const save = useMutation({
    mutationFn: () =>
      aiApi.setBudget({
        is_enabled: enabled,
        monthly_limit_cents: monthly || '0',
        per_run_limit_cents: perRun || '0',
      }),
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.aiBudget, result)
      toast.success('Teto de gasto atualizado.')
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar o teto.'),
  })

  if (budget.isLoading) return <Skeleton className="h-64" />
  const data = budget.data
  if (!data) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CircleDollarSign /> Teto de gasto com IA
        </CardTitle>
        <CardDescription>
          Os limites ficam aqui, não no código. Zero em um campo quer dizer “sem teto para este”.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-border p-3">
            <p className="game-label text-[0.6rem] text-muted">Gasto no mês</p>
            <p className="mt-1 text-xl font-extrabold text-white tabular-nums">
              {toReais(data.spent_month_cents)}
            </p>
          </div>
          <div className="rounded-lg border border-border p-3">
            <p className="game-label text-[0.6rem] text-muted">Chamadas no mês</p>
            <p className="mt-1 text-xl font-extrabold text-white tabular-nums">
              {data.calls_month.toLocaleString('pt-BR')}
            </p>
          </div>
          <div className="rounded-lg border border-border p-3">
            <p className="game-label text-[0.6rem] text-muted">Corte</p>
            <p className="mt-1 text-sm font-semibold text-white">
              {data.is_enabled ? 'Ligado' : 'Desligado'}
            </p>
            <p className="text-[0.68rem] text-muted">
              {data.is_enabled ? 'barra ao estourar' : 'só medindo'}
            </p>
          </div>
        </div>

        {!data.is_complete && (
          // Um total menor que o real é pior que nenhum total.
          <Alert tone="warning" title="Este total está incompleto">
            <p className="flex items-start gap-2">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>
                Estes modelos foram usados no mês e não têm preço cadastrado, então o consumo
                deles não vira dinheiro na conta:{' '}
                <strong>{data.models_without_price.join(', ')}</strong>. Cadastre o preço por 1k
                tokens para o teto valer de verdade.
              </span>
            </p>
          </Alert>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Teto mensal (centavos)" htmlFor="budget-monthly">
            <Input
              id="budget-monthly"
              inputMode="decimal"
              value={monthly}
              onChange={(event) => setMonthly(event.target.value)}
            />
            {/* O campo é em centavos; o equivalente em reais evita um erro de
                duas ordens de grandeza em algo que corta gasto de verdade. */}
            <p className="mt-1 text-xs text-muted">{describeLimit(monthly)}</p>
          </Field>
          <Field label="Teto por execução (centavos)" htmlFor="budget-run">
            <Input
              id="budget-run"
              inputMode="decimal"
              value={perRun}
              onChange={(event) => setPerRun(event.target.value)}
            />
            <p className="mt-1 text-xs text-muted">{describeLimit(perRun)}</p>
          </Field>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Toggle
              checked={enabled}
              onChange={setEnabled}
              label="Cortar quando passar do teto"
            />
            <span className="text-sm text-foreground">Cortar quando passar do teto</span>
          </div>
          <Button onClick={() => save.mutate()} disabled={save.isPending}>
            Salvar teto
          </Button>
        </div>

        <p className="text-xs text-muted">
          O custo de uma chamada só é conhecido depois dela, então o corte barra a{' '}
          <strong>próxima</strong> chamada depois do estouro. O excesso máximo é de uma chamada —
          preferimos isso a estimar tokens por um número inventado.
        </p>
      </CardContent>
    </Card>
  )
}

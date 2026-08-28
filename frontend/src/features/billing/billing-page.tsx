import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Receipt } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SkeletonList } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { billingApi } from '@/lib/api/billing'
import { queryKeys } from '@/lib/query-client'
import { formatPrice } from './format'
import { PlanCard } from './components/plan-card'
import { UsageList } from './components/usage-list'

export function BillingPage() {
  const queryClient = useQueryClient()
  const [coupon, setCoupon] = useState('')

  const plans = useQuery({
    queryKey: queryKeys.billingPlans,
    queryFn: () => billingApi.plans(),
  })
  const subscription = useQuery({
    queryKey: queryKeys.billingSubscription,
    queryFn: () => billingApi.subscription(),
  })
  const usage = useQuery({
    queryKey: queryKeys.billingUsage,
    queryFn: () => billingApi.usage(),
  })
  const invoices = useQuery({
    queryKey: queryKeys.billingInvoices,
    queryFn: () => billingApi.invoices(),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['billing'] })
  const fail = (error: unknown) =>
    toast.error(error instanceof ApiError ? error.message : 'Não foi possível concluir.')

  const subscribe = useMutation({
    mutationFn: (slug: string) =>
      billingApi.subscribe({ plan_slug: slug, coupon_code: coupon || undefined }),
    onSuccess: (result) => {
      invalidate()
      toast.success(result.detail)
    },
    onError: fail,
  })

  const change = useMutation({
    mutationFn: (slug: string) => billingApi.changePlan(slug),
    onSuccess: (result) => {
      invalidate()
      toast.success(result.reason)
    },
    onError: fail,
  })

  const cancel = useMutation({
    mutationFn: () => billingApi.cancel(),
    onSuccess: (result) => {
      invalidate()
      toast.success(result.status_label)
    },
    onError: fail,
  })

  if (plans.isLoading) return <SkeletonList rows={3} />
  if (plans.isError) return <ErrorState error={plans.error} onRetry={() => plans.refetch()} />

  const current = subscription.data
  const hasSubscription = current !== undefined && current.status !== 'NONE'

  return (
    <div className="space-y-6">
      <PageHeader
        title="Plano e cobrança"
        description="O que cada plano concede, o que você já usou e quanto custa."
      />

      {current && (
        <Card>
          <CardHeader>
            <CardTitle>
              {current.plan_name}
              <Badge variant={current.is_paid ? 'primary' : 'neutral'} className="ml-2">
                {current.status_label}
              </Badge>
            </CardTitle>
            {current.current_period_end && (
              <CardDescription className="flex items-center gap-1.5">
                <CalendarClock className="size-3.5" aria-hidden />
                Período atual até{' '}
                {new Date(current.current_period_end).toLocaleDateString('pt-BR')}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent className="space-y-4">
            {current.scheduled_plan_slug && (
              <p className="rounded-md bg-info-soft/40 p-3 text-sm">
                Troca agendada para <strong>{current.scheduled_plan_slug}</strong> na virada do
                período. Você mantém o plano de hoje até lá.
              </p>
            )}
            {current.status === 'CANCELING' && current.current_period_end && (
              <p className="rounded-md bg-warning-soft/40 p-3 text-sm">
                Assinatura cancelada. O acesso continua até{' '}
                {new Date(current.current_period_end).toLocaleDateString('pt-BR')} — você pagou
                por esse período.
              </p>
            )}
            {current.status === 'PAST_DUE' && current.grace_ends_on && (
              <p className="rounded-md bg-warning-soft/40 p-3 text-sm">
                Pagamento pendente. O acesso continua até{' '}
                {new Date(current.grace_ends_on).toLocaleDateString('pt-BR')} para dar tempo de
                resolver.
              </p>
            )}

            {hasSubscription && current.is_paid && current.status !== 'CANCELING' && (
              <Button
                variant="ghost"
                onClick={() => cancel.mutate()}
                disabled={cancel.isPending}
              >
                Cancelar assinatura
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Meu uso</CardTitle>
          <CardDescription>
            Os limites vêm do plano contratado e renovam na data indicada.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {usage.isLoading && <SkeletonList rows={3} />}
          {usage.data && <UsageList items={usage.data} />}
        </CardContent>
      </Card>

      <div className="space-y-3">
        <div className="flex flex-wrap items-end gap-2">
          <label className="space-y-1 text-sm">
            <span className="text-muted">Cupom (opcional)</span>
            <Input
              value={coupon}
              maxLength={40}
              placeholder="Código"
              onChange={(event) => setCoupon(event.target.value.toUpperCase())}
              className="max-w-[14rem]"
            />
          </label>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {plans.data!.map((plan) => (
            <PlanCard
              key={plan.slug}
              plan={plan}
              current={current?.plan_slug === plan.slug}
              disabled={subscribe.isPending || change.isPending}
              onChoose={(slug) =>
                hasSubscription ? change.mutate(slug) : subscribe.mutate(slug)
              }
            />
          ))}
        </div>
      </div>

      {invoices.data && invoices.data.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Receipt className="size-4" aria-hidden />
              Faturamento
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {invoices.data.map((item) => (
                <li
                  key={`${item.description}-${item.created_at}`}
                  className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-2 text-sm last:border-b-0 last:pb-0"
                >
                  <span>
                    {item.description}
                    <span className="ml-2 text-xs text-subtle">
                      {new Date(item.created_at).toLocaleDateString('pt-BR')}
                    </span>
                  </span>
                  <span className="font-mono tabular-nums">
                    {formatPrice(item.total_cents)}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

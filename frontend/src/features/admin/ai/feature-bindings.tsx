import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { Toggle } from '@/components/ui/toggle'
import { ErrorState } from '@/components/feedback/error-state'
import { aiApi } from '@/lib/api/ai'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/query-client'
import type { AIProvider } from '@/lib/api/types'

/** Um modelo por funcionalidade — trocável sem tocar em código. */
export function FeatureBindings({ providers }: { providers: AIProvider[] }) {
  const queryClient = useQueryClient()
  const features = useQuery({ queryKey: queryKeys.aiFeatures, queryFn: aiApi.features })

  const update = useMutation({
    mutationFn: (input: {
      feature: string
      provider_slug: string | null
      model_slug: string | null
      is_enabled: boolean
    }) =>
      aiApi.setFeature(input.feature, {
        provider_slug: input.provider_slug,
        model_slug: input.model_slug,
        is_enabled: input.is_enabled,
      }),
    onSuccess: () => {
      toast.success('Configuração atualizada.')
      queryClient.invalidateQueries({ queryKey: queryKeys.aiFeatures })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar.'),
  })

  const options = providers.flatMap((provider) =>
    provider.models
      .filter((model) => model.is_active)
      .map((model) => ({
        value: `${provider.slug}::${model.slug}`,
        label: `${model.slug} · ${provider.display_name}`,
        kind: model.kind,
      })),
  )

  if (features.isLoading) return <SkeletonList rows={4} />
  if (features.isError) {
    return <ErrorState error={features.error} onRetry={() => features.refetch()} />
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Modelo por funcionalidade</CardTitle>
        <CardDescription>
          Cada recurso da plataforma escolhe seu próprio modelo. Enquanto uma funcionalidade
          estiver desligada, ela simplesmente não chama a IA — e nada é cobrado.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {features.data?.map((feature) => {
          const current =
            feature.provider_slug && feature.model_slug
              ? `${feature.provider_slug}::${feature.model_slug}`
              : ''
          const allowed = options.filter((option) =>
            feature.feature === 'embeddings.default'
              ? option.kind === 'embedding'
              : feature.feature === 'rerank.default'
                ? option.kind !== 'embedding'
                : option.kind === 'chat',
          )

          return (
            <div
              key={feature.feature}
              className="flex flex-col gap-3 border-b border-border/60 pb-4 last:border-0 last:pb-0 lg:flex-row lg:items-center"
            >
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-medium">
                  {feature.label}
                  <Badge variant="outline">{feature.feature}</Badge>
                </p>
                <p className="text-sm text-muted">{feature.description}</p>
              </div>

              <div className="flex items-center gap-3 lg:w-96">
                <Select
                  aria-label={`Modelo para ${feature.label}`}
                  value={current}
                  disabled={allowed.length === 0 || update.isPending}
                  onChange={(event) => {
                    const [providerSlug, modelSlug] = event.target.value.split('::')
                    update.mutate({
                      feature: feature.feature,
                      provider_slug: providerSlug || null,
                      model_slug: modelSlug || null,
                      is_enabled: feature.is_enabled && Boolean(event.target.value),
                    })
                  }}
                >
                  <option value="">
                    {allowed.length === 0 ? 'nenhum modelo importado' : 'não configurado'}
                  </option>
                  {allowed.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
                <Toggle
                  checked={feature.is_enabled}
                  disabled={!feature.model_slug || update.isPending}
                  label={`Habilitar ${feature.label}`}
                  onChange={(value) =>
                    update.mutate({
                      feature: feature.feature,
                      provider_slug: feature.provider_slug,
                      model_slug: feature.model_slug,
                      is_enabled: value,
                    })
                  }
                />
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

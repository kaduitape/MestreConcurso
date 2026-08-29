import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plug, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { aiApi } from '@/lib/api/ai'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/query-client'
import { ProviderCard } from './provider-card'
import { FeatureBindings } from './feature-bindings'
import { CacheCard } from './cache-card'

const PROVIDER_LABELS: Record<string, string> = {
  aisa: 'AISA.one',
  openai: 'OpenAI (ChatGPT)',
  anthropic: 'Anthropic (Claude)',
  gemini: 'Google (Gemini)',
}

export function AiSection() {
  const queryClient = useQueryClient()
  const providers = useQuery({ queryKey: queryKeys.aiProviders, queryFn: aiApi.providers })
  const available = useQuery({ queryKey: queryKeys.aiAvailable, queryFn: aiApi.available })

  const connect = useMutation({
    mutationFn: (slug: string) => aiApi.createProvider(slug),
    onSuccess: () => {
      toast.success('Provedor cadastrado. Informe a chave para ativá-lo.')
      queryClient.invalidateQueries({ queryKey: ['admin', 'ai'] })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível cadastrar.'),
  })

  const pending = (available.data?.available ?? []).filter(
    (slug) => !(available.data?.configured ?? []).includes(slug),
  )

  if (providers.isLoading) return <SkeletonList rows={3} />
  if (providers.isError) {
    return <ErrorState error={providers.error} onRetry={() => providers.refetch()} />
  }

  return (
    <div className="space-y-6">
      <Alert tone="info" title="Como a plataforma usa a IA">
        A chave fica cifrada no banco e nunca volta pela API. O que for apurado — perfil de
        banca, análise de edital, classificação de questão — é gravado no banco e reutilizado: a
        IA só é chamada quando não existe resposta válida guardada.
      </Alert>

      {providers.data?.length === 0 && (
        <EmptyState
          icon={Sparkles}
          title="Nenhum provedor de IA conectado"
          description="Conecte um provedor para habilitar recursos de IA. AISA.one também permite usar modelos OpenAI, Claude e Gemini com uma única chave."
          action={
            <div className="flex flex-wrap gap-2">
              <Button loading={connect.isPending} onClick={() => connect.mutate('aisa')}>
                <Plug /> Conectar AISA.one
              </Button>
              <Button variant="outline" loading={connect.isPending} onClick={() => connect.mutate('openai')}>
                <Plug /> Conectar OpenAI
              </Button>
            </div>
          }
        />
      )}

      {providers.data?.map((provider) => (
        <ProviderCard key={provider.slug} provider={provider} />
      ))}

      {pending.length > 0 && providers.data && providers.data.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-dashed border-border p-4">
          <span className="text-sm text-muted">Outros provedores disponíveis:</span>
          {pending.map((slug) => (
            <Button
              key={slug}
              variant="outline"
              size="sm"
              loading={connect.isPending}
              onClick={() => connect.mutate(slug)}
            >
              <Plug /> {PROVIDER_LABELS[slug] ?? slug}
            </Button>
          ))}
        </div>
      )}

      <FeatureBindings providers={providers.data ?? []} />
      <CacheCard />
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, KeyRound, PlugZap, RefreshCw, ShieldAlert, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Toggle } from '@/components/ui/toggle'
import { aiApi } from '@/lib/api/ai'
import { ApiError } from '@/lib/api/client'
import type { AIProvider, ConnectionCheck } from '@/lib/api/types'

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString('pt-BR') : '—'
}

export function ProviderCard({ provider }: { provider: AIProvider }) {
  const queryClient = useQueryClient()
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState(provider.base_url ?? '')
  const [check, setCheck] = useState<ConnectionCheck | null>(null)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'ai'] })

  useEffect(() => setBaseUrl(provider.base_url ?? ''), [provider.base_url])

  const saveEndpoint = useMutation({
    mutationFn: () => aiApi.updateProvider(provider.slug, { base_url: baseUrl.trim() || null }),
    onSuccess: () => {
      toast.success('Endpoint salvo.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível salvar o endpoint.'),
  })

  const saveKey = useMutation({
    mutationFn: () => aiApi.setKey(provider.slug, apiKey.trim()),
    onSuccess: () => {
      setApiKey('')
      setCheck(null)
      toast.success('Chave gravada com segurança (cifrada no banco).')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível salvar a chave.',
      ),
  })

  const removeKey = useMutation({
    mutationFn: () => aiApi.removeKey(provider.slug),
    onSuccess: () => {
      toast.success('Chave removida. O provedor foi desativado.')
      setCheck(null)
      invalidate()
    },
  })

  const testConnection = useMutation({
    mutationFn: () => aiApi.testProvider(provider.slug),
    onSuccess: (result) => {
      setCheck(result)
      toast.success(`Conexão OK — ${result.models_available} modelo(s) disponíveis.`)
      invalidate()
    },
    onError: (error: unknown) => {
      setCheck(null)
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível falar com o provedor.',
      )
      invalidate()
    },
  })

  const syncModels = useMutation({
    mutationFn: () => aiApi.syncModels(provider.slug),
    onSuccess: (models) => {
      toast.success(`${models.length} modelo(s) importado(s).`)
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Falha ao importar modelos.'),
  })

  const toggleActive = useMutation({
    mutationFn: (value: boolean) => aiApi.updateProvider(provider.slug, { is_active: value }),
    onSuccess: () => invalidate(),
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível alterar.'),
  })

  const chatModels = provider.models.filter((model) => model.kind === 'chat')
  const embeddingModels = provider.models.filter((model) => model.kind === 'embedding')

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              {provider.display_name}
              {provider.is_active ? (
                <Badge variant="success">Ativo</Badge>
              ) : (
                <Badge variant="neutral">Inativo</Badge>
              )}
            </CardTitle>
            <CardDescription>
              {provider.base_url ?? 'endpoint padrão do provedor'}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted">Habilitado</span>
            <Toggle
              checked={provider.is_active}
              disabled={!provider.has_api_key || toggleActive.isPending}
              onChange={(value) => toggleActive.mutate(value)}
              label={`Ativar ${provider.display_name}`}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="grid gap-3 rounded-md bg-surface-muted p-4 sm:grid-cols-3">
          <div>
            <p className="text-xs tracking-wide text-subtle uppercase">Chave de API</p>
            <p className="text-sm font-medium">
              {provider.has_api_key ? provider.api_key_hint : 'não cadastrada'}
            </p>
          </div>
          <div>
            <p className="text-xs tracking-wide text-subtle uppercase">Cadastrada em</p>
            <p className="text-sm">{formatDate(provider.api_key_set_at)}</p>
          </div>
          <div>
            <p className="text-xs tracking-wide text-subtle uppercase">Último teste</p>
            <p className="text-sm">
              {provider.last_test_status === 'OK' && (
                <span className="text-success">OK · {formatDate(provider.last_tested_at)}</span>
              )}
              {provider.last_test_status === 'FAILED' && (
                <span className="text-danger">
                  Falhou · {formatDate(provider.last_tested_at)}
                </span>
              )}
              {!provider.last_test_status && '—'}
            </p>
          </div>
        </div>

        {provider.last_test_status === 'FAILED' && provider.last_test_message && (
          <Alert tone="danger" title="Último teste falhou">
            {provider.last_test_message}
          </Alert>
        )}

        <form
          className="flex flex-col gap-2 sm:flex-row sm:items-end"
          onSubmit={(event) => {
            event.preventDefault()
            saveEndpoint.mutate()
          }}
        >
          <Field
            className="flex-1"
            label="Base URL"
            htmlFor={`base-url-${provider.slug}`}
            hint="Para AISA.one, use https://api.aisa.one/v1."
          >
            <Input
              id={`base-url-${provider.slug}`}
              type="url"
              inputMode="url"
              autoComplete="off"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
            />
          </Field>
          <Button type="submit" variant="outline" loading={saveEndpoint.isPending}>
            Salvar endpoint
          </Button>
        </form>

        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault()
            saveKey.mutate()
          }}
        >
          <Field
            label={provider.has_api_key ? 'Substituir a chave de API' : 'Chave de API'}
            htmlFor={`key-${provider.slug}`}
            hint="A chave é cifrada antes de ser gravada e nunca é devolvida pela API."
          >
            <Input
              id={`key-${provider.slug}`}
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="sk-proj-…"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              loading={saveKey.isPending}
              disabled={apiKey.trim().length < 20}
            >
              <KeyRound /> {provider.has_api_key ? 'Substituir chave' : 'Salvar chave'}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!provider.has_api_key}
              loading={testConnection.isPending}
              onClick={() => testConnection.mutate()}
            >
              <PlugZap /> Testar conexão
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!provider.has_api_key}
              loading={syncModels.isPending}
              onClick={() => syncModels.mutate()}
            >
              <RefreshCw /> Importar modelos
            </Button>
            {provider.has_api_key && (
              <Button
                type="button"
                variant="ghost"
                className="text-danger"
                loading={removeKey.isPending}
                onClick={() => removeKey.mutate()}
              >
                <Trash2 /> Remover chave
              </Button>
            )}
          </div>
        </form>

        {check?.ok && (
          <Alert tone="success" title="Conexão verificada agora">
            <p className="flex items-center gap-2">
              <CheckCircle2 className="size-4" aria-hidden />
              {check.models_available} modelo(s) disponíveis · {check.latency_ms} ms
            </p>
            {check.sample_models.length > 0 && (
              <p className="mt-1 text-xs">Exemplos: {check.sample_models.join(', ')}</p>
            )}
          </Alert>
        )}

        {provider.models.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-semibold tracking-wide text-subtle uppercase">
                Modelos de texto ({chatModels.length})
              </p>
              <ul className="max-h-40 space-y-1 overflow-y-auto text-sm">
                {chatModels.map((model) => (
                  <li key={model.slug} className="flex items-center justify-between gap-2">
                    <span className="truncate">{model.slug}</span>
                    <span className="shrink-0 text-xs text-subtle">
                      {model.input_cost_per_1k
                        ? `US$ ${model.input_cost_per_1k}/1k`
                        : 'preço não informado'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-2 text-xs font-semibold tracking-wide text-subtle uppercase">
                Modelos de embedding ({embeddingModels.length})
              </p>
              <ul className="max-h-40 space-y-1 overflow-y-auto text-sm">
                {embeddingModels.map((model) => (
                  <li key={model.slug} className="truncate">
                    {model.slug}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <Alert tone="info">
            <span className="flex items-center gap-2">
              <ShieldAlert className="size-4" aria-hidden />
              Nenhum modelo importado ainda. Use “Importar modelos” para trazer a lista real que
              a sua chave pode acessar.
            </span>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}

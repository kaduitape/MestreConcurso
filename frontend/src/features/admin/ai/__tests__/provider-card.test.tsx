import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'
import { ProviderCard } from '../provider-card'
import type { AIProvider } from '@/lib/api/types'

const base: AIProvider = {
  slug: 'openai',
  display_name: 'OpenAI (ChatGPT)',
  base_url: 'https://api.openai.com/v1',
  organization: null,
  is_active: false,
  has_api_key: false,
  api_key_hint: null,
  api_key_set_at: null,
  last_tested_at: null,
  last_test_status: null,
  last_test_message: null,
  models: [],
}

function renderCard(provider: AIProvider) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ProviderCard provider={provider} />
    </QueryClientProvider>,
  )
}

describe('ProviderCard', () => {
  it('indica quando não há chave cadastrada', () => {
    renderCard(base)
    expect(screen.getByText('não cadastrada')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Testar conexão/ })).toBeDisabled()
    expect(screen.getByRole('switch')).toBeDisabled()
  })

  it('mostra apenas a dica da chave, nunca o valor completo', () => {
    renderCard({
      ...base,
      has_api_key: true,
      api_key_hint: 'sk-…7890',
      is_active: true,
    })
    expect(screen.getByText('sk-…7890')).toBeInTheDocument()
    expect(screen.getByRole('switch')).toBeEnabled()
    expect(screen.getByRole('button', { name: /Testar conexão/ })).toBeEnabled()
  })

  it('avisa quando nenhum modelo foi importado', () => {
    renderCard({ ...base, has_api_key: true, api_key_hint: 'sk-…7890' })
    expect(screen.getByText(/Nenhum modelo importado ainda/)).toBeInTheDocument()
  })

  it('exibe a falha do último teste', () => {
    renderCard({
      ...base,
      has_api_key: true,
      api_key_hint: 'sk-…7890',
      last_test_status: 'FAILED',
      last_test_message: 'Chave de API inválida ou sem permissão.',
      last_tested_at: '2026-08-23T12:00:00Z',
    })
    expect(screen.getByText('Último teste falhou')).toBeInTheDocument()
    expect(screen.getByText('Chave de API inválida ou sem permissão.')).toBeInTheDocument()
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiRequest, tokenStorage } from '@/lib/api/client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('apiRequest', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('envia o access token quando existe', async () => {
    tokenStorage.save({
      access_token: 'token-de-acesso',
      refresh_token: 'token-de-renovacao',
      token_type: 'bearer',
      expires_in: 900,
      session_id: 'SESSION',
    })
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiRequest('/users/me')

    const headers = (fetchMock.mock.calls[0]![1] as RequestInit).headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer token-de-acesso')
  })

  it('renova o token e repete a requisição depois de um 401', async () => {
    tokenStorage.save({
      access_token: 'expirado',
      refresh_token: 'renovacao',
      token_type: 'bearer',
      expires_in: 900,
      session_id: 'SESSION',
    })

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: 'token_expired', message: 'Token expirado.', details: {} } },
          401,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'novo',
          refresh_token: 'nova-renovacao',
          token_type: 'bearer',
          expires_in: 900,
          session_id: 'SESSION',
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ email: 'a@b.com.br' }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await apiRequest<{ email: string }>('/users/me')

    expect(result.email).toBe('a@b.com.br')
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(tokenStorage.access).toBe('novo')
  })

  it('converte o envelope de erro da API em ApiError', async () => {
    // Cada chamada precisa de uma resposta nova: o corpo só pode ser lido uma vez.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(
          {
            error: {
              code: 'weak_password',
              message: 'A senha não atende à política.',
              details: { requirements: ['ao menos um número'] },
              request_id: 'abc123',
            },
          },
          422,
        ),
      ),
    )

    await expect(
      apiRequest('/auth/register', { method: 'POST', skipAuth: true }),
    ).rejects.toThrow(ApiError)

    try {
      await apiRequest('/auth/register', { method: 'POST', skipAuth: true })
    } catch (error) {
      const apiError = error as ApiError
      expect(apiError.code).toBe('weak_password')
      expect(apiError.requestId).toBe('abc123')
      expect(apiError.fieldMessages).toEqual(['ao menos um número'])
    }
  })
})

describe('renovação de token', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  function sessao() {
    tokenStorage.save({
      access_token: 'expirado',
      refresh_token: 'renovacao-1',
      token_type: 'bearer',
      expires_in: 900,
      session_id: 'SESSION',
    })
  }

  it('não derruba a sessão quando a renovação não alcança o servidor', async () => {
    // O defeito: oscilação de rede durante a renovação limpava os tokens e
    // levava o usuário para a tela de login no meio do trabalho.
    sessao()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'x', message: 'y' } }, 401))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest('/users/me')).rejects.toBeInstanceOf(ApiError)

    // Os tokens continuam onde estavam: "não deu para perguntar" não é
    // "o servidor disse não".
    expect(tokenStorage.refresh).toBe('renovacao-1')
    expect(tokenStorage.access).toBe('expirado')
  })

  it('derruba a sessão quando o servidor recusa a renovação', async () => {
    sessao()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'x', message: 'y' } }, 401))
      .mockResolvedValueOnce(
        jsonResponse({ error: { code: 'refresh_token_reuse', message: 'reuso' } }, 401),
      )
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest('/users/me')).rejects.toBeInstanceOf(ApiError)

    expect(tokenStorage.refresh).toBeNull()
  })

  it('usa o token que outra aba acabou de renovar, sem pedir outro', async () => {
    // O servidor rotaciona o refresh token e trata reapresentação como roubo:
    // duas abas renovando com o mesmo token matavam a família de sessões. Com
    // a fila compartilhada, a segunda aba aproveita o token da primeira.
    sessao()
    localStorage.setItem('mestre.refresh_lock', String(Date.now()))

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'x', message: 'y' } }, 401))
      .mockResolvedValueOnce(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    const pedido = apiRequest<{ ok: boolean }>('/users/me')
    // A "outra aba" conclui a renovação e grava o token novo.
    await new Promise((resolve) => setTimeout(resolve, 10))
    tokenStorage.save({
      access_token: 'renovado-por-outra-aba',
      refresh_token: 'renovacao-2',
      token_type: 'bearer',
      expires_in: 900,
      session_id: 'SESSION',
    })
    localStorage.removeItem('mestre.refresh_lock')

    await expect(pedido).resolves.toEqual({ ok: true })

    // Nenhuma chamada a /auth/refresh: só o 401 e a repetição.
    const urls = fetchMock.mock.calls.map((call) => String(call[0]))
    expect(urls.filter((url) => url.includes('/auth/refresh'))).toHaveLength(0)
    const headers = (fetchMock.mock.calls[1]![1] as RequestInit).headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer renovado-por-outra-aba')
  })

  it('renova uma vez só quando vários pedidos recebem 401 juntos', async () => {
    sessao()
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes('/auth/refresh')) {
        return jsonResponse({
          access_token: 'novo',
          refresh_token: 'renovacao-2',
          token_type: 'bearer',
          expires_in: 900,
          session_id: 'SESSION',
        })
      }
      const headers = init?.headers as Headers | undefined
      if (headers?.get('Authorization') === 'Bearer expirado') {
        return jsonResponse({ error: { code: 'x', message: 'y' } }, 401)
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    await Promise.all([
      apiRequest('/users/me'),
      apiRequest('/users/me'),
      apiRequest('/users/me'),
    ])

    const refreshes = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes('/auth/refresh'),
    )
    expect(refreshes).toHaveLength(1)
    // E a fila é liberada no fim, para o próximo 401 poder renovar.
    expect(localStorage.getItem('mestre.refresh_lock')).toBeNull()
  })

  it('uma fila abandonada não impede a renovação para sempre', async () => {
    // Aba fechada no meio da renovação deixaria o registro para trás.
    sessao()
    localStorage.setItem('mestre.refresh_lock', String(Date.now() - 60_000))

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'x', message: 'y' } }, 401))
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: 'novo',
          refresh_token: 'renovacao-2',
          token_type: 'bearer',
          expires_in: 900,
          session_id: 'SESSION',
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest<{ ok: boolean }>('/users/me')).resolves.toEqual({ ok: true })
    expect(tokenStorage.access).toBe('novo')
  })
})

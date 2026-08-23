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

    await expect(apiRequest('/auth/register', { method: 'POST', skipAuth: true })).rejects.toThrow(
      ApiError,
    )

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

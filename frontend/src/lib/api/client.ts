/**
 * Cliente HTTP da aplicação.
 *
 * Responsabilidades: anexar o access token, renovar automaticamente quando ele
 * expira (uma única renovação concorrente, com fila) e normalizar os erros da API
 * no mesmo envelope usado pelo backend.
 */
import type { ApiErrorBody, TokenPair } from './types'

const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
const BASE = `${API_URL}/api/v1`
const ACCESS_KEY = 'mestre.access_token'
const REFRESH_KEY = 'mestre.refresh_token'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>
  readonly requestId: string | null

  constructor(status: number, body: ApiErrorBody['error']) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.details = body.details ?? {}
    this.requestId = body.request_id
  }

  /** Lista legível de requisitos de senha ou campos inválidos, quando houver. */
  get fieldMessages(): string[] {
    const requirements = this.details.requirements
    if (Array.isArray(requirements)) return requirements.map(String)
    const fields = this.details.fields
    if (Array.isArray(fields)) {
      return fields.map((item) => {
        const entry = item as { field?: string; message?: string }
        return entry.field ? `${entry.field}: ${entry.message}` : String(entry.message)
      })
    }
    return []
  }
}

export const tokenStorage = {
  get access() {
    return localStorage.getItem(ACCESS_KEY)
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY)
  },
  save(tokens: TokenPair) {
    localStorage.setItem(ACCESS_KEY, tokens.access_token)
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

type Listener = () => void
const unauthorizedListeners = new Set<Listener>()

/** Notifica a aplicação quando a sessão deixa de ser válida. */
export function onUnauthorized(listener: Listener): () => void {
  unauthorizedListeners.add(listener)
  return () => unauthorizedListeners.delete(listener)
}

function notifyUnauthorized() {
  tokenStorage.clear()
  unauthorizedListeners.forEach((listener) => listener())
}

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStorage.refresh
  if (!refresh) return null

  refreshPromise ??= (async () => {
    try {
      const response = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      })
      if (!response.ok) {
        notifyUnauthorized()
        return null
      }
      const tokens = (await response.json()) as TokenPair
      tokenStorage.save(tokens)
      return tokens.access_token
    } catch {
      return null
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  /** Rotas públicas (login, registro) não devem disparar renovação de token. */
  skipAuth?: boolean
  raw?: boolean
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ApiErrorBody
    if (body?.error) return new ApiError(response.status, body.error)
  } catch {
    /* resposta sem corpo JSON */
  }
  return new ApiError(response.status, {
    code: 'network_error',
    message: 'Não foi possível concluir a operação. Tente novamente.',
    details: {},
    request_id: null,
  })
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, skipAuth, raw, headers, ...rest } = options

  const send = async (token: string | null): Promise<Response> => {
    const finalHeaders = new Headers(headers)
    if (body !== undefined && !finalHeaders.has('Content-Type')) {
      finalHeaders.set('Content-Type', 'application/json')
    }
    if (token && !skipAuth) finalHeaders.set('Authorization', `Bearer ${token}`)

    return fetch(`${BASE}${path}`, {
      ...rest,
      headers: finalHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  }

  let response: Response
  try {
    response = await send(tokenStorage.access)
  } catch {
    throw new ApiError(0, {
      code: 'network_unreachable',
      message: 'Servidor indisponível. Verifique sua conexão.',
      details: {},
      request_id: null,
    })
  }

  if (response.status === 401 && !skipAuth && tokenStorage.refresh) {
    const renewed = await refreshAccessToken()
    if (renewed) {
      response = await send(renewed)
    } else {
      notifyUnauthorized()
    }
  }

  if (!response.ok) throw await parseError(response)
  if (raw) return response as unknown as T
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'POST', body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PUT', body }),
  delete: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'DELETE', body }),
}

export { API_URL, BASE as API_BASE }

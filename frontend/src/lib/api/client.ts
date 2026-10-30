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

/**
 * Renovação de token, com três cuidados que faltavam.
 *
 * O servidor rotaciona o refresh token e **detecta reuso**: apresentar o mesmo
 * token duas vezes derruba a família de sessões inteira, porque isso é o que um
 * token roubado pareceria. É a decisão de segurança certa, e nada aqui a
 * enfraquece — o que mudou é o cliente deixar de cometer esse reuso.
 *
 * 1. **A fila atravessa abas.** `localStorage` é compartilhado, mas a variável
 *    de fila era por aba: duas abas expirando juntas apresentavam o mesmo
 *    token, o servidor via reuso e matava a sessão no meio do trabalho. Agora a
 *    fila é um registro em `localStorage`, com prazo, que as abas respeitam.
 * 2. **Falha de rede não é sessão inválida.** O `catch` devolvia nulo e quem
 *    chamava limpava os tokens: uma oscilação de rede derrubava a sessão e o
 *    formulário em andamento. Agora "não deu para perguntar" e "o servidor
 *    disse não" são resultados diferentes.
 * 3. **Token que outra aba já renovou é reaproveitado.** Depois de esperar a
 *    fila, o cliente relê o armazenamento: se o access token mudou, ele serve,
 *    e não há segunda renovação para gerar reuso.
 */
const LOCK_KEY = 'mestre.refresh_lock'
/** Depois disso a fila é considerada abandonada (aba fechada no meio). */
const LOCK_TTL_MS = 10_000
const LOCK_POLL_MS = 120

/** O que a renovação concluiu. Distinguir os três é o ponto. */
type RefreshOutcome =
  { kind: 'renewed'; token: string } | { kind: 'rejected' } | { kind: 'unreachable' }

let refreshPromise: Promise<RefreshOutcome> | null = null

function readLock(): number {
  try {
    return Number(localStorage.getItem(LOCK_KEY) ?? 0)
  } catch {
    return 0
  }
}

/** Tenta ficar com a fila. Falso quando outra aba está renovando agora. */
function acquireLock(): boolean {
  try {
    const agora = Date.now()
    const atual = readLock()
    if (atual && agora - atual < LOCK_TTL_MS) return false
    localStorage.setItem(LOCK_KEY, String(agora))
    return true
  } catch {
    // Sem armazenamento (aba privada, cookies bloqueados) a fila entre abas
    // não existe. Seguir em frente é melhor que não renovar nunca.
    return true
  }
}

function releaseLock(): void {
  try {
    localStorage.removeItem(LOCK_KEY)
  } catch {
    /* nada a liberar */
  }
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

async function postRefresh(token: string): Promise<RefreshOutcome> {
  let response: Response
  try {
    response = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: token }),
    })
  } catch {
    // Não deu para perguntar. Os tokens continuam onde estão.
    return { kind: 'unreachable' }
  }
  if (!response.ok) return { kind: 'rejected' }
  try {
    const tokens = (await response.json()) as TokenPair
    tokenStorage.save(tokens)
    return { kind: 'renewed', token: tokens.access_token }
  } catch {
    return { kind: 'unreachable' }
  }
}

async function runRefresh(previousAccess: string | null): Promise<RefreshOutcome> {
  // Espera a fila de outra aba. Enquanto ela renova, este cliente não toca no
  // token — é exatamente o reuso que derrubava a família de sessões.
  const limite = Date.now() + LOCK_TTL_MS
  while (!acquireLock() && Date.now() < limite) {
    await sleep(LOCK_POLL_MS)
    const atual = tokenStorage.access
    if (atual && atual !== previousAccess) {
      // A outra aba conseguiu. O token novo serve, e não há segunda chamada.
      return { kind: 'renewed', token: atual }
    }
  }

  try {
    const atual = tokenStorage.access
    if (atual && atual !== previousAccess) return { kind: 'renewed', token: atual }
    const refresh = tokenStorage.refresh
    if (!refresh) return { kind: 'rejected' }
    return await postRefresh(refresh)
  } finally {
    releaseLock()
  }
}

async function refreshAccessToken(previousAccess: string | null): Promise<RefreshOutcome> {
  if (!tokenStorage.refresh) return { kind: 'rejected' }
  // Dentro da aba, uma renovação só: quem chega durante ela entra na fila.
  refreshPromise ??= runRefresh(previousAccess).finally(() => {
    refreshPromise = null
  })
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

  const isFormData = body instanceof FormData

  const send = async (token: string | null): Promise<Response> => {
    const finalHeaders = new Headers(headers)
    // O navegador precisa definir o boundary do multipart sozinho.
    if (body !== undefined && !isFormData && !finalHeaders.has('Content-Type')) {
      finalHeaders.set('Content-Type', 'application/json')
    }
    if (token && !skipAuth) finalHeaders.set('Authorization', `Bearer ${token}`)

    return fetch(`${BASE}${path}`, {
      ...rest,
      headers: finalHeaders,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    })
  }

  // O token usado nesta tentativa fica guardado: é com ele que se descobre, no
  // 401, se outra aba já renovou enquanto este pedido estava no ar.
  const usado = tokenStorage.access
  let response: Response
  try {
    response = await send(usado)
  } catch {
    throw new ApiError(0, {
      code: 'network_unreachable',
      message: 'Servidor indisponível. Verifique sua conexão.',
      details: {},
      request_id: null,
    })
  }

  if (response.status === 401 && !skipAuth && tokenStorage.refresh) {
    const resultado = await refreshAccessToken(usado)
    if (resultado.kind === 'renewed') {
      response = await send(resultado.token)
    } else if (resultado.kind === 'rejected') {
      // O servidor disse não: a sessão acabou de verdade.
      notifyUnauthorized()
    }
    // 'unreachable' não derruba a sessão: o erro de rede sobe como erro de
    // rede, e quem estava preenchendo um formulário pode tentar de novo.
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

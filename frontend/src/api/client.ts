import type { ApiInfo, ChatResponse, Health, SessionInfo, UploadResponse } from './types'

// Same origin in production (the gateway serves the app); the Vite dev server proxies /api.
const BASE = import.meta.env.VITE_API_URL ?? '/api'

// Agents can be slow (video indexing, document embedding), so chat and upload get a long timeout.
const SHORT_TIMEOUT_MS = 15_000
const LONG_TIMEOUT_MS = 180_000

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = SHORT_TIMEOUT_MS): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { ...init, signal: AbortSignal.timeout(timeoutMs) })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      throw new ApiError(0, 'The server took too long to answer. Try again in a moment.')
    }
    throw new ApiError(0, "Can't reach the chatbot server. Is it running?")
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return (await response.json()) as T
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    // FastAPI puts HTTPException messages in `detail`; validation errors are a list.
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg
  } catch {
    // not JSON
  }
  return `Request failed (${response.status})`
}

export const api = {
  info: () => request<ApiInfo>(''),

  health: () => request<Health>('/health'),

  chat: (sessionId: string, query: string) =>
    request<ChatResponse>(
      '/chat',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, query }),
      },
      LONG_TIMEOUT_MS,
    ),

  upload: (sessionId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    form.append('session_id', sessionId)
    return request<UploadResponse>('/upload', { method: 'POST', body: form }, LONG_TIMEOUT_MS)
  },

  session: (sessionId: string) => request<SessionInfo>(`/sessions/${encodeURIComponent(sessionId)}`),

  clearSession: (sessionId: string) =>
    request<{ success: boolean }>(`/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' }, 30_000),
}

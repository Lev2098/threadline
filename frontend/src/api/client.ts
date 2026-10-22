import {
  ApiError,
  type ApiErrorBody,
  type Captcha,
  type Comment,
  type CommentPage,
  type Ordering,
  type ThreadSlice,
} from './types'

const BASE = '/api/v1'
const TOKEN_KEY = 'threadline.token'

let token: string | null = readToken()
let pendingSession: Promise<string> | null = null

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function storeToken(value: string | null): void {
  token = value
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* private mode: keep token in memory only */
  }
}

/** Forget the current token (expired or rejected); the next call fetches a new one. */
export function resetToken(): void {
  storeToken(null)
}

/** Anonymous JWT identifying this browser; fetched once and reused. */
export async function ensureToken(): Promise<string> {
  if (token) return token
  pendingSession ??= fetch(`${BASE}/session`, { method: 'POST' })
    .then(async (r) => {
      if (!r.ok) throw new Error('session')
      const body = (await r.json()) as { token: string }
      storeToken(body.token)
      return body.token
    })
    .finally(() => (pendingSession = null))
  return pendingSession
}

async function request<T>(path: string, init: RequestInit = {}, auth = false, retried = false): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (auth || token) headers.set('Authorization', `Bearer ${auth ? await ensureToken() : token}`)

  const response = await fetch(`${BASE}${path}`, { ...init, headers })
  if (response.status === 401 && !retried) {
    storeToken(null) // expired or rotated secret: get a fresh identity once
    return request<T>(path, init, true, true)
  }
  if (!response.ok) {
    let body: ApiErrorBody = { code: 'error', message: response.statusText, errors: {} }
    try {
      body = await response.json()
    } catch {
      /* non-JSON error page from a proxy */
    }
    throw new ApiError(response.status, body)
  }
  return (await response.json()) as T
}

export const api = {
  listComments: (page: number, ordering: Ordering) =>
    request<CommentPage>(`/comments?page=${page}&ordering=${encodeURIComponent(ordering)}`),

  comment: (id: number) => request<Comment>(`/comments/${id}`),

  thread: (rootId: number, cursor?: string | null) =>
    request<ThreadSlice>(`/comments/${rootId}/thread${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`),

  search: (q: string, page = 1) => request<CommentPage>(`/comments/search?q=${encodeURIComponent(q)}&page=${page}`),

  captcha: () => request<Captcha>('/captcha', { cache: 'no-store' }),

  preview: (text: string) =>
    request<{ html: string }>('/comments/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),

  post: (form: FormData) => request<Comment>('/comments', { method: 'POST', body: form }, true),

  token: ensureToken,
}

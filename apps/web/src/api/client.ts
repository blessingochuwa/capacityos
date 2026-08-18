/**
 * The single place that talks HTTP to apps/api. Every typed API module
 * (./entities.ts, features/capacity/api/capacityApi.ts) goes through this —
 * no raw fetch() calls anywhere else in the app (CLAUDE.md §6/§28: routes
 * orchestrate, they don't reimplement transport concerns per call site).
 *
 * Phase 10: every request carries `credentials: 'include'` so the httpOnly
 * session cookie (and the readable CSRF cookie) are sent with same-site
 * requests; every mutating request additionally echoes the CSRF cookie back
 * as an X-CSRF-Token header (double-submit defense-in-depth — see
 * docs/adr/0010-authentication-rbac-audit.md). A 401 from ANY request
 * (except the login endpoint itself, which handles its own failure inline)
 * invokes the registered unauthorized handler — see setUnauthorizedHandler,
 * called once by features/auth/context/AuthProvider.tsx.
 */

const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const CSRF_COOKIE_NAME = 'capacityos_csrf'
const LOGIN_PATH = '/api/v1/auth/login'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Registered by AuthProvider on mount — reacts to a 401 from anywhere in
 * the app (session expired mid-use, cookie cleared, etc.) by clearing
 * cached session state and redirecting to /login. Kept as a simple
 * settable callback, not a React context, since this module is plain
 * functions with no component tree of its own. */
let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

function readCsrfCookie(): string | null {
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${CSRF_COOKIE_NAME}=`))
  return match ? decodeURIComponent(match.slice(CSRF_COOKIE_NAME.length + 1)) : null
}

/** FastAPI error bodies come in two shapes: domain errors (app/core/exceptions.py)
 * always send `{"detail": "a plain message"}`; FastAPI's own request-validation
 * errors (e.g. a malformed query param) send `{"detail": [{"msg": "...", ...}]}`.
 * Both are normalized to one readable string here so callers never branch on it. */
function extractDetail(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) {
    return null
  }
  const detail = (body as { detail: unknown }).detail
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((entry) =>
        typeof entry === 'object' && entry !== null && 'msg' in entry
          ? String((entry as { msg: unknown }).msg)
          : null,
      )
      .filter((msg): msg is string => msg !== null)
    return messages.length > 0 ? messages.join('; ') : null
  }
  return null
}

export type QueryParams = Record<string, string | number | undefined>

function buildQueryString(params?: QueryParams): string {
  if (!params) return ''
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      search.set(key, String(value))
    }
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

async function handleResponse<T>(response: Response, path: string): Promise<T> {
  if (!response.ok) {
    if (response.status === 401 && path !== LOGIN_PATH) {
      unauthorizedHandler?.()
    }
    let detail: string | null = null
    try {
      detail = extractDetail(await response.json())
    } catch {
      // Response body wasn't JSON — fall through to the generic message below.
    }
    throw new ApiError(
      response.status,
      detail ?? `Request failed (${response.status})`,
    )
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

const MUTATING_METHODS = new Set(['POST', 'PATCH', 'DELETE'])

async function request<T>(
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
  path: string,
  options?: { params?: QueryParams; body?: unknown },
): Promise<T> {
  const url = `${API_BASE_URL}${path}${buildQueryString(options?.params)}`
  const init: RequestInit = {
    method,
    credentials: 'include',
    headers: { Accept: 'application/json' },
  }
  if (options?.body !== undefined) {
    init.headers = { ...init.headers, 'Content-Type': 'application/json' }
    init.body = JSON.stringify(options.body)
  }
  if (MUTATING_METHODS.has(method)) {
    const csrfToken = readCsrfCookie()
    if (csrfToken) {
      init.headers = { ...init.headers, 'X-CSRF-Token': csrfToken }
    }
  }

  let response: Response
  try {
    response = await fetch(url, init)
  } catch {
    throw new ApiError(
      0,
      'Could not reach the CapacityOS API. Check your connection.',
    )
  }
  return handleResponse<T>(response, path)
}

export function apiGet<T>(path: string, params?: QueryParams): Promise<T> {
  return request<T>('GET', path, { params })
}

/** Scenario planning (Phase 4) is the first frontend feature that writes —
 * every earlier phase was read-only. These follow apiGet's exact error-
 * handling shape (same ApiError, same extractDetail) rather than
 * introducing a second convention. */
export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, { body })
}

export function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PATCH', path, { body })
}

export function apiDelete<T = void>(path: string): Promise<T> {
  return request<T>('DELETE', path)
}

/** Phase 6 import upload — the only place this app sends a multipart body
 * instead of JSON, so it can't reuse request()'s JSON-only Content-Type
 * handling. Deliberately omits a Content-Type header: the browser sets the
 * multipart boundary itself from the FormData instance, which a hand-set
 * header would break. */
export async function apiPostFormData<T>(
  path: string,
  formData: FormData,
  params?: QueryParams,
): Promise<T> {
  const url = `${API_BASE_URL}${path}${buildQueryString(params)}`
  const csrfToken = readCsrfCookie()
  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      },
      body: formData,
    })
  } catch {
    throw new ApiError(
      0,
      'Could not reach the CapacityOS API. Check your connection.',
    )
  }
  return handleResponse<T>(response, path)
}

/** Extracts the server-suggested filename from a
 * `Content-Disposition: attachment; filename="x.csv"` header — falls back
 * to `fallback` if the header is missing or unparseable. */
function filenameFromContentDisposition(
  header: string | null,
  fallback: string,
): string {
  if (!header) return fallback
  const match = /filename="?([^";]+)"?/.exec(header)
  return match?.[1] ?? fallback
}

/** Phase 6 export/template download — the response body is a raw file
 * (CSV/JSON), never a JSON API envelope, so it can't reuse handleResponse's
 * response.json() parsing. */
export async function apiGetBlob(
  path: string,
  params?: QueryParams,
): Promise<{ blob: Blob; filename: string }> {
  const url = `${API_BASE_URL}${path}${buildQueryString(params)}`
  let response: Response
  try {
    response = await fetch(url, { method: 'GET', credentials: 'include' })
  } catch {
    throw new ApiError(
      0,
      'Could not reach the CapacityOS API. Check your connection.',
    )
  }
  if (!response.ok) {
    if (response.status === 401) {
      unauthorizedHandler?.()
    }
    let detail: string | null = null
    try {
      detail = extractDetail(await response.json())
    } catch {
      // Response body wasn't JSON — fall through to the generic message below.
    }
    throw new ApiError(
      response.status,
      detail ?? `Request failed (${response.status})`,
    )
  }
  const blob = await response.blob()
  const filename = filenameFromContentDisposition(
    response.headers.get('Content-Disposition'),
    'download',
  )
  return { blob, filename }
}

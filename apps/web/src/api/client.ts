/**
 * The single place that talks HTTP to apps/api. Every typed API module
 * (./entities.ts, features/capacity/api/capacityApi.ts) goes through this —
 * no raw fetch() calls anywhere else in the app (CLAUDE.md §6/§28: routes
 * orchestrate, they don't reimplement transport concerns per call site).
 */

const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
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

export async function apiGet<T>(
  path: string,
  params?: QueryParams,
): Promise<T> {
  const url = `${API_BASE_URL}${path}${buildQueryString(params)}`

  let response: Response
  try {
    response = await fetch(url, { headers: { Accept: 'application/json' } })
  } catch {
    throw new ApiError(
      0,
      'Could not reach the CapacityOS API. Check your connection.',
    )
  }

  if (!response.ok) {
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

  return (await response.json()) as T
}

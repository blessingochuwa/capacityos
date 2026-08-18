import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  apiDelete,
  apiGet,
  apiPost,
  setUnauthorizedHandler,
} from './client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api client (Phase 10)', () => {
  beforeEach(() => {
    document.cookie = 'capacityos_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setUnauthorizedHandler(null)
    document.cookie = 'capacityos_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
  })

  it('sends credentials: include on every request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiGet('/api/v1/people')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ credentials: 'include' }),
    )
  })

  it('echoes the CSRF cookie as an X-CSRF-Token header on a mutating request', async () => {
    document.cookie = 'capacityos_csrf=abc123'
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiPost('/api/v1/people', { name: 'Alex' })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe(
      'abc123',
    )
  })

  it('does not send an X-CSRF-Token header on a GET request', async () => {
    document.cookie = 'capacityos_csrf=abc123'
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiGet('/api/v1/people')

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(
      (init.headers as Record<string, string> | undefined)?.['X-CSRF-Token'],
    ).toBeUndefined()
  })

  it('invokes the registered unauthorized handler on a 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'nope' }, 401)),
    )
    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await expect(apiGet('/api/v1/people')).rejects.toThrow()
    expect(handler).toHaveBeenCalledOnce()
  })

  it('does NOT invoke the unauthorized handler for a failed login attempt', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: 'Invalid email or password.' }, 401),
        ),
    )
    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await expect(
      apiPost('/api/v1/auth/login', { email: 'a@b.com', password: 'x' }),
    ).rejects.toThrow()
    expect(handler).not.toHaveBeenCalled()
  })

  it('does not invoke the unauthorized handler on a 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Forbidden.' }, 403)),
    )
    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await expect(apiDelete('/api/v1/people/1')).rejects.toThrow()
    expect(handler).not.toHaveBeenCalled()
  })
})

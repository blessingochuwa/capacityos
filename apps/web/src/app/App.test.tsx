import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

const CURRENT_USER_PAYLOAD = {
  id: 'user-1',
  email: 'owner@example.com',
  display_name: 'Owner Person',
  status: 'active',
  role: 'owner',
  person_id: null,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  permissions: ['person.read', 'export.use'],
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects to the login page when there is no session (Phase 10)', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: 'Authentication required.' }, 401),
        ),
    )
    render(<App />)
    expect(await screen.findByText('CapacityOS')).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: /sign in/i }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('renders the authenticated shell and primary navigation once a session exists', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url.includes('/api/v1/auth/me')
            ? jsonResponse(CURRENT_USER_PAYLOAD)
            : jsonResponse({ items: [], total: 0 }),
        ),
      ),
    )
    render(<App />)
    expect(await screen.findByText('CapacityOS')).toBeInTheDocument()
    expect(
      await screen.findByRole('navigation', { name: 'Primary' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Capacity' })).toBeInTheDocument()
    expect(screen.getByText('Owner Person')).toBeInTheDocument()
  })
})

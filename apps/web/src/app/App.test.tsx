import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { queryClient } from '@/lib/queryClient'
import App from './App'

const CURRENT_USER_PAYLOAD = {
  id: 'user-1',
  email: 'owner@example.com',
  display_name: 'Owner Person',
  status: 'active',
  role: 'owner',
  active_organization: { id: 'org-1', name: 'Test Organization', slug: 'test-org' },
  organizations: [{ id: 'org-1', name: 'Test Organization', slug: 'test-org' }],
  person_id: null,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  permissions: ['person.read', 'export.use'],
  accessible_team_ids: [],
  accessible_project_ids: [],
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
    // The app's queryClient is a module-level singleton (see App.tsx) — the
    // session query has `staleTime: Infinity`, so a successful result from
    // one test would otherwise be served as "fresh" to the next test's
    // fresh <App /> render instead of triggering a new fetch against that
    // test's own mocked response.
    queryClient.clear()
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

  it('redirects to organization selection when authenticated with no active organization (Phase 12)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url.includes('/api/v1/auth/me')
            ? jsonResponse({
                ...CURRENT_USER_PAYLOAD,
                role: null,
                active_organization: null,
                organizations: [],
                permissions: [],
              })
            : jsonResponse({ items: [], total: 0 }),
        ),
      ),
    )
    render(<App />)
    expect(await screen.findByText('Create an organization')).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })
})

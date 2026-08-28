import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiError } from '@/api/client'
import { makeCurrentUser } from '@/test/fixtures'
import { AuthProvider, useAuth } from './AuthContext'
import { authApi } from '../api/authApi'

vi.mock('../api/authApi')

const mockedAuthApi = vi.mocked(authApi)

function renderWithAuth() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  function Probe() {
    const { user, status, can, canManageResource } = useAuth()
    return (
      <div>
        <span data-testid="status">{status}</span>
        <span data-testid="email">{user?.email ?? 'none'}</span>
        <span data-testid="can-write">
          {can('person.write') ? 'yes' : 'no'}
        </span>
        <span data-testid="can-manage-team-a">
          {canManageResource('team', 'team-a') ? 'yes' : 'no'}
        </span>
        <span data-testid="can-manage-team-b">
          {canManageResource('team', 'team-b') ? 'yes' : 'no'}
        </span>
      </div>
    )
  }

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

describe('AuthProvider', () => {
  it('reports unauthenticated when the session check returns 401', async () => {
    mockedAuthApi.me.mockRejectedValue(new ApiError(401, 'Not logged in.'))
    renderWithAuth()

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent(
        'unauthenticated',
      ),
    )
    expect(screen.getByTestId('email')).toHaveTextContent('none')
  })

  it('reports authenticated with the current user when the session is valid', async () => {
    mockedAuthApi.me.mockResolvedValue(makeCurrentUser({ email: 'a@b.com' }))
    renderWithAuth()

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated'),
    )
    expect(screen.getByTestId('email')).toHaveTextContent('a@b.com')
  })

  it('can() reflects the current user permissions, denying everything before login', async () => {
    mockedAuthApi.me.mockRejectedValue(new ApiError(401, 'Not logged in.'))
    renderWithAuth()

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent(
        'unauthenticated',
      ),
    )
    expect(screen.getByTestId('can-write')).toHaveTextContent('no')
  })

  it('reports no-organization when the session is valid but has no active organization (Phase 12)', async () => {
    mockedAuthApi.me.mockResolvedValue(
      makeCurrentUser({ role: null, active_organization: null, permissions: [] }),
    )
    renderWithAuth()

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('no-organization'),
    )
  })
})

describe('switchOrganization (Phase 12)', () => {
  it('re-fetches the session with the new organization and purges other cached queries', async () => {
    const initialUser = makeCurrentUser({
      active_organization: { id: 'org-1', name: 'Org One', slug: 'org-one', is_active: true },
      organizations: [
        { id: 'org-1', name: 'Org One', slug: 'org-one', is_active: true },
        { id: 'org-2', name: 'Org Two', slug: 'org-two', is_active: true },
      ],
    })
    const switchedUser = makeCurrentUser({
      active_organization: { id: 'org-2', name: 'Org Two', slug: 'org-two', is_active: true },
      organizations: initialUser.organizations,
      role: 'viewer',
      permissions: ['person.read'],
    })
    mockedAuthApi.me.mockResolvedValue(initialUser)
    mockedAuthApi.switchOrganization.mockResolvedValue(switchedUser)

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    queryClient.setQueryData(['other-scoped-query'], { stale: true })

    function Probe() {
      const { user, status, switchOrganization } = useAuth()
      return (
        <div>
          <span data-testid="status">{status}</span>
          <span data-testid="active-org">{user?.active_organization?.id ?? 'none'}</span>
          <button onClick={() => void switchOrganization('org-2')}>Switch</button>
        </div>
      )
    }

    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Probe />
        </AuthProvider>
      </QueryClientProvider>,
    )

    await waitFor(() =>
      expect(screen.getByTestId('active-org')).toHaveTextContent('org-1'),
    )

    screen.getByRole('button', { name: 'Switch' }).click()

    await waitFor(() =>
      expect(screen.getByTestId('active-org')).toHaveTextContent('org-2'),
    )
    expect(mockedAuthApi.switchOrganization.mock.calls[0]?.[0]).toBe('org-2')
    expect(queryClient.getQueryData(['other-scoped-query'])).toBeUndefined()
  })
})

describe('canManageResource (Phase 11)', () => {
  it('always allows Owner, even with no accessible_team_ids at all', async () => {
    mockedAuthApi.me.mockResolvedValue(
      makeCurrentUser({ role: 'owner', accessible_team_ids: [] }),
    )
    renderWithAuth()

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated'),
    )
    expect(screen.getByTestId('can-manage-team-a')).toHaveTextContent('yes')
    expect(screen.getByTestId('can-manage-team-b')).toHaveTextContent('yes')
  })

  it('always allows Admin, even with no accessible_team_ids at all', async () => {
    mockedAuthApi.me.mockResolvedValue(
      makeCurrentUser({ role: 'admin', accessible_team_ids: [] }),
    )
    renderWithAuth()

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated'),
    )
    expect(screen.getByTestId('can-manage-team-a')).toHaveTextContent('yes')
  })

  it('allows a Manager only for teams present in accessible_team_ids', async () => {
    mockedAuthApi.me.mockResolvedValue(
      makeCurrentUser({
        role: 'manager',
        permissions: ['team.read', 'team.write'],
        accessible_team_ids: ['team-a'],
      }),
    )
    renderWithAuth()

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated'),
    )
    expect(screen.getByTestId('can-manage-team-a')).toHaveTextContent('yes')
    expect(screen.getByTestId('can-manage-team-b')).toHaveTextContent('no')
  })

  it('denies a Manager with no team.write permission even if the id is listed', async () => {
    mockedAuthApi.me.mockResolvedValue(
      makeCurrentUser({
        role: 'manager',
        permissions: ['team.read'],
        accessible_team_ids: ['team-a'],
      }),
    )
    renderWithAuth()

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated'),
    )
    expect(screen.getByTestId('can-manage-team-a')).toHaveTextContent('no')
  })

  it('denies Member/Viewer regardless of accessible_team_ids', async () => {
    mockedAuthApi.me.mockResolvedValue(
      makeCurrentUser({
        role: 'viewer',
        permissions: ['team.read'],
        accessible_team_ids: ['team-a'],
      }),
    )
    renderWithAuth()

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('authenticated'),
    )
    expect(screen.getByTestId('can-manage-team-a')).toHaveTextContent('no')
  })
})

describe('useAuth outside AuthProvider', () => {
  it('returns a safe, fully-denied default instead of throwing', () => {
    function Probe() {
      const { status, can, canManageResource } = useAuth()
      return (
        <div>
          <span data-testid="status">{status}</span>
          <span data-testid="can-write">
            {can('person.write') ? 'yes' : 'no'}
          </span>
          <span data-testid="can-manage">
            {canManageResource('team', 'team-a') ? 'yes' : 'no'}
          </span>
        </div>
      )
    }
    render(<Probe />)
    expect(screen.getByTestId('status')).toHaveTextContent('unauthenticated')
    expect(screen.getByTestId('can-write')).toHaveTextContent('no')
    expect(screen.getByTestId('can-manage')).toHaveTextContent('no')
  })
})

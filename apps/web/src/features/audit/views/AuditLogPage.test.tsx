import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '@/api/client'
import { useAuth } from '@/features/auth/context/AuthContext'
import { useMemberships } from '@/features/members/hooks/useMemberships'
import { mockQueryError, mockQueryPending, mockQuerySuccess } from '@/test/mockQueryResult'
import { makeAuditEvent } from '@/test/fixtures'
import type { CurrentUser } from '@/features/auth/types/auth'
import type { Membership } from '@/features/members/types/members'
import { AuditLogPage } from './AuditLogPage'
import { useAuditEvents } from '../hooks/useAuditEvents'

vi.mock('@/features/auth/context/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('@/features/members/hooks/useMemberships')
vi.mock('../hooks/useAuditEvents')

const mockedUseAuth = vi.mocked(useAuth)
const mockedUseMemberships = vi.mocked(useMemberships)
const mockedUseAuditEvents = vi.mocked(useAuditEvents)

function authValue(overrides: Partial<ReturnType<typeof useAuth>> = {}): ReturnType<
  typeof useAuth
> {
  return {
    user: {
      active_organization: { id: 'org-1', name: 'Acme', slug: 'acme', is_active: true },
    } as CurrentUser,
    status: 'authenticated',
    can: (permission: string) => permission === 'audit.read',
    canManageResource: () => true,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganization: vi.fn(),
    ...overrides,
  }
}

const MEMBER: Membership = {
  id: 'membership-1',
  organization_id: 'org-1',
  user_id: 'user-1',
  email: 'ada@acme.test',
  display_name: 'Ada Lovelace',
  role: 'admin',
  status: 'active',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('AuditLogPage', () => {
  it('shows a view-only notice for a role without audit.read', () => {
    mockedUseAuth.mockReturnValue(authValue({ can: () => false }))
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    render(<AuditLogPage />)

    expect(
      screen.getByText("Your role doesn't include permission to view the audit log."),
    ).toBeInTheDocument()
    expect(screen.queryByText('Events')).not.toBeInTheDocument()
  })

  it('renders the page for an authorized role and lists events', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [MEMBER], total: 1 }))
    mockedUseAuditEvents.mockReturnValue(
      mockQuerySuccess({
        items: [makeAuditEvent({ actor_email: 'ada@acme.test' })],
        total: 1,
      }),
    )

    render(<AuditLogPage />)

    expect(screen.getByRole('heading', { name: 'Audit log' })).toBeInTheDocument()
    expect(screen.getByText('ada@acme.test')).toBeInTheDocument()
  })

  it('shows the loading state while events are pending', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(mockQueryPending())

    render(<AuditLogPage />)

    expect(screen.getByText('Loading audit events…')).toBeInTheDocument()
  })

  it('surfaces an API error instead of a generic empty state', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(mockQueryError(new ApiError(500, 'Request failed (500)')))

    render(<AuditLogPage />)

    expect(screen.getByText('Request failed (500)')).toBeInTheDocument()
    expect(screen.queryByText('No audit events yet.')).not.toBeInTheDocument()
  })

  it('shows the empty state when no audit events exist', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    render(<AuditLogPage />)

    expect(screen.getByText('No audit events yet.')).toBeInTheDocument()
  })

  it('populates the actor filter from the active organization roster', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [MEMBER], total: 1 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    render(<AuditLogPage />)

    expect(mockedUseMemberships).toHaveBeenCalledWith('org-1')
    expect(screen.getByLabelText('Actor')).toHaveTextContent('Ada Lovelace (ada@acme.test)')
  })

  it('selecting an actor filters the events query by actor_user_id', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [MEMBER], total: 1 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    const user = userEvent.setup()
    render(<AuditLogPage />)

    await user.selectOptions(screen.getByLabelText('Actor'), 'user-1')

    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ actor_user_id: 'user-1', offset: 0 }),
    )
  })

  it('does not paginate when every event fits on one page', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(
      mockQuerySuccess({ items: [makeAuditEvent()], total: 1 }),
    )

    render(<AuditLogPage />)

    expect(screen.getByText('Showing 1–1 of 1 event')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('advances to the next page and requests the next offset', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(
      mockQuerySuccess({
        items: Array.from({ length: 50 }, (_, i) => makeAuditEvent({ id: `event-${i}` })),
        total: 120,
      }),
    )

    const user = userEvent.setup()
    render(<AuditLogPage />)

    expect(screen.getByText('Showing 1–50 of 120 events')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 50 }),
    )
  })
})

import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
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

  it('renders Action and Resource type filter inputs alongside the existing actor/date filters', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    render(<AuditLogPage />)

    expect(screen.getByLabelText('Actor')).toBeInTheDocument()
    expect(screen.getByLabelText('Action')).toBeInTheDocument()
    expect(screen.getByLabelText('Resource type')).toBeInTheDocument()
    expect(screen.getByLabelText('Since')).toBeInTheDocument()
    expect(screen.getByLabelText('Until')).toBeInTheDocument()
  })

  it('typing an Action value includes it in the audit events request', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    const user = userEvent.setup()
    render(<AuditLogPage />)

    await user.type(screen.getByLabelText('Action'), 'person.create')

    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ action: 'person.create', offset: 0 }),
    )
  })

  it('typing a Resource type value includes it in the audit events request', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    const user = userEvent.setup()
    render(<AuditLogPage />)

    await user.type(screen.getByLabelText('Resource type'), 'project')

    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ resource_type: 'project', offset: 0 }),
    )
  })

  it('combines actor, action, resource type, and date filters into one request', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [MEMBER], total: 1 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    const user = userEvent.setup()
    render(<AuditLogPage />)

    await user.selectOptions(screen.getByLabelText('Actor'), 'user-1')
    await user.type(screen.getByLabelText('Action'), 'person.create')
    await user.type(screen.getByLabelText('Resource type'), 'person')
    fireEvent.change(screen.getByLabelText('Since'), { target: { value: '2026-01-01T00:00' } })

    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({
        actor_user_id: 'user-1',
        action: 'person.create',
        resource_type: 'person',
        start: new Date('2026-01-01T00:00').toISOString(),
        offset: 0,
      }),
    )
  })

  it('resets pagination to the first page when the Action filter changes', async () => {
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

    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 50 }),
    )

    await user.type(screen.getByLabelText('Action'), 'x')
    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ action: 'x', offset: 0 }),
    )
  })

  it('resets pagination to the first page when the Resource type filter changes', async () => {
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

    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 50 }),
    )

    await user.type(screen.getByLabelText('Resource type'), 'x')
    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ resource_type: 'x', offset: 0 }),
    )
  })

  it('clearing the Action field removes it from the request', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    const user = userEvent.setup()
    render(<AuditLogPage />)

    const action = screen.getByLabelText('Action')
    await user.type(action, 'person.create')
    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ action: 'person.create' }),
    )

    await user.clear(action)
    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ action: undefined }),
    )
  })

  it('clearing the Resource type field removes it from the request', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    const user = userEvent.setup()
    render(<AuditLogPage />)

    const resourceType = screen.getByLabelText('Resource type')
    await user.type(resourceType, 'project')
    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ resource_type: 'project' }),
    )

    await user.clear(resourceType)
    expect(mockedUseAuditEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ resource_type: undefined }),
    )
  })

  it('shows the filtered-empty state, not the "no history" state, when an Action filter matches nothing', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUseMemberships.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseAuditEvents.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    const user = userEvent.setup()
    render(<AuditLogPage />)

    await user.type(screen.getByLabelText('Action'), 'nonexistent.action')

    expect(screen.getByText('No audit events match these filters.')).toBeInTheDocument()
    expect(screen.queryByText('No audit events yet.')).not.toBeInTheDocument()
  })
})

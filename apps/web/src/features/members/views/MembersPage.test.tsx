import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuth } from '@/features/auth/context/AuthContext'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import type { CurrentUser } from '@/features/auth/types/auth'
import { MembersPage } from './MembersPage'
import {
  useAddMember,
  useChangeMemberRole,
  useMemberships,
  useReactivateMember,
  useRevokeMember,
} from '../hooks/useMemberships'
import type { Membership } from '../types/members'

vi.mock('@/features/auth/context/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('../hooks/useMemberships')

const mockedUseAuth = vi.mocked(useAuth)
const mockedUseMemberships = vi.mocked(useMemberships)
const mockedUseAddMember = vi.mocked(useAddMember)
const mockedUseChangeMemberRole = vi.mocked(useChangeMemberRole)
const mockedUseRevokeMember = vi.mocked(useRevokeMember)
const mockedUseReactivateMember = vi.mocked(useReactivateMember)

function authValue(overrides: Partial<ReturnType<typeof useAuth>> = {}): ReturnType<
  typeof useAuth
> {
  return {
    user: {
      active_organization: { id: 'org-1', name: 'Acme', slug: 'acme' },
    } as CurrentUser,
    status: 'authenticated',
    can: (permission: string) => permission === 'membership.manage',
    canManageResource: () => true,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganization: vi.fn(),
    ...overrides,
  }
}

const IDLE_MUTATION = {
  mutate: vi.fn(),
  mutateAsync: vi.fn().mockResolvedValue(undefined),
  isPending: false,
  isError: false,
  error: null,
  variables: undefined,
}

function mockMutations() {
  mockedUseAddMember.mockReturnValue({
    ...IDLE_MUTATION,
  } as unknown as ReturnType<typeof useAddMember>)
  mockedUseChangeMemberRole.mockReturnValue({
    ...IDLE_MUTATION,
  } as unknown as ReturnType<typeof useChangeMemberRole>)
  mockedUseRevokeMember.mockReturnValue({
    ...IDLE_MUTATION,
  } as unknown as ReturnType<typeof useRevokeMember>)
  mockedUseReactivateMember.mockReturnValue({
    ...IDLE_MUTATION,
  } as unknown as ReturnType<typeof useReactivateMember>)
}

const MEMBERS: Membership[] = [
  {
    id: 'm-1',
    organization_id: 'org-1',
    user_id: 'user-1',
    email: 'ada@acme.test',
    display_name: 'Ada Lovelace',
    role: 'owner',
    status: 'active',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'm-2',
    organization_id: 'org-1',
    user_id: 'user-2',
    email: 'alan@acme.test',
    display_name: 'Alan Turing',
    role: 'manager',
    status: 'active',
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
]

describe('MembersPage', () => {
  it('shows a view-only notice for a role without membership.manage', () => {
    mockedUseAuth.mockReturnValue(authValue({ can: () => false }))
    mockMutations()
    mockedUseMemberships.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )

    render(<MembersPage />)

    expect(
      screen.getByText(
        "Your role doesn't include permission to manage this organization's members.",
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('Organization members')).not.toBeInTheDocument()
  })

  it('prompts to select an organization when none is active', () => {
    mockedUseAuth.mockReturnValue(
      authValue({ user: { active_organization: null } as CurrentUser }),
    )
    mockMutations()
    mockedUseMemberships.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )

    render(<MembersPage />)

    expect(
      screen.getByText('Select an organization to manage its members.'),
    ).toBeInTheDocument()
  })

  it('lists members and wires role change and revoke to their mutations', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockMutations()
    const changeRole = vi.fn()
    const revoke = vi.fn()
    mockedUseChangeMemberRole.mockReturnValue({
      ...IDLE_MUTATION,
      mutate: changeRole,
    } as unknown as ReturnType<typeof useChangeMemberRole>)
    mockedUseRevokeMember.mockReturnValue({
      ...IDLE_MUTATION,
      mutate: revoke,
    } as unknown as ReturnType<typeof useRevokeMember>)
    mockedUseMemberships.mockReturnValue(
      mockQuerySuccess({ items: MEMBERS, total: 2 }),
    )

    const user = userEvent.setup()
    render(<MembersPage />)

    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument()
    expect(screen.getByText('alan@acme.test')).toBeInTheDocument()

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Role for Alan Turing' }),
      'admin',
    )
    expect(changeRole).toHaveBeenCalledWith({ userId: 'user-2', role: 'admin' })

    const revokeButtons = screen.getAllByRole('button', { name: 'Revoke' })
    await user.click(revokeButtons[1])
    expect(revoke).toHaveBeenCalledWith('user-2')
  })

  it('surfaces an add-member error from the mutation', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockMutations()
    mockedUseAddMember.mockReturnValue({
      ...IDLE_MUTATION,
      isError: true,
      error: new Error('User not found: nobody@acme.test'),
    } as unknown as ReturnType<typeof useAddMember>)
    mockedUseMemberships.mockReturnValue(
      mockQuerySuccess({ items: MEMBERS, total: 2 }),
    )

    render(<MembersPage />)

    expect(screen.getByRole('alert')).toHaveTextContent(
      'User not found: nobody@acme.test',
    )
  })
})

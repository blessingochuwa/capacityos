import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MembersTable } from './MembersTable'
import type { Membership } from '../types/members'

function membership(overrides: Partial<Membership> = {}): Membership {
  return {
    id: `m-${overrides.user_id ?? '1'}`,
    organization_id: 'org-1',
    user_id: 'user-1',
    email: 'ada@acme.test',
    display_name: 'Ada Lovelace',
    role: 'admin',
    status: 'active',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('MembersTable', () => {
  it('renders an empty state when there are no members', () => {
    render(
      <MembersTable
        memberships={[]}
        onRoleChange={vi.fn()}
        onRevoke={vi.fn()}
        onReactivate={vi.fn()}
      />,
    )
    expect(
      screen.getByText('This organization has no members yet.'),
    ).toBeInTheDocument()
  })

  it('shows each member with their email, role, and status', () => {
    render(
      <MembersTable
        memberships={[
          membership(),
          membership({
            user_id: 'user-2',
            display_name: 'Grace Hopper',
            email: 'grace@acme.test',
            role: 'viewer',
            status: 'revoked',
          }),
        ]}
        onRoleChange={vi.fn()}
        onRevoke={vi.fn()}
        onReactivate={vi.fn()}
      />,
    )
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument()
    expect(screen.getByText('grace@acme.test')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Role for Ada Lovelace' })).toHaveValue(
      'admin',
    )
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Revoked')).toBeInTheDocument()
  })

  it('calls onRoleChange with the picked role', async () => {
    const onRoleChange = vi.fn()
    const user = userEvent.setup()
    render(
      <MembersTable
        memberships={[membership()]}
        onRoleChange={onRoleChange}
        onRevoke={vi.fn()}
        onReactivate={vi.fn()}
      />,
    )
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Role for Ada Lovelace' }),
      'manager',
    )
    expect(onRoleChange).toHaveBeenCalledWith('user-1', 'manager')
  })

  it('revokes an active member and reactivates a revoked one', async () => {
    const onRevoke = vi.fn()
    const onReactivate = vi.fn()
    const user = userEvent.setup()
    render(
      <MembersTable
        memberships={[
          membership(),
          membership({ user_id: 'user-2', display_name: 'Grace Hopper', status: 'revoked' }),
        ]}
        onRoleChange={vi.fn()}
        onRevoke={onRevoke}
        onReactivate={onReactivate}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Revoke' }))
    expect(onRevoke).toHaveBeenCalledWith('user-1')
    await user.click(screen.getByRole('button', { name: 'Reactivate' }))
    expect(onReactivate).toHaveBeenCalledWith('user-2')
  })

  it('disables the in-flight row and shows its action error only on that row', () => {
    render(
      <MembersTable
        memberships={[
          membership(),
          membership({ user_id: 'user-2', display_name: 'Grace Hopper', role: 'owner' }),
        ]}
        onRoleChange={vi.fn()}
        onRevoke={vi.fn()}
        onReactivate={vi.fn()}
        pendingUserId="user-1"
        actionError={{
          userId: 'user-2',
          message: 'Cannot demote the last remaining Owner of this organization.',
        }}
      />,
    )
    expect(
      screen.getByRole('combobox', { name: 'Role for Ada Lovelace' }),
    ).toBeDisabled()
    expect(
      screen.getByText('Cannot demote the last remaining Owner of this organization.'),
    ).toBeInTheDocument()
    // The error is scoped to Grace's row, not Ada's.
    expect(screen.getByRole('button', { name: 'Revoke' })).toBeEnabled()
  })
})

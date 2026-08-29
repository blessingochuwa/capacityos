import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UsersTable } from './UsersTable'
import type { UserAccount } from '../types/users'

function account(overrides: Partial<UserAccount> = {}): UserAccount {
  return {
    id: 'user-1',
    email: 'ada@acme.test',
    display_name: 'Ada Lovelace',
    status: 'active',
    person_id: null,
    last_login_at: '2026-02-01T09:30:00Z',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('UsersTable', () => {
  it('renders an empty state when there are no accounts', () => {
    render(
      <UsersTable
        users={[]}
        personLabels={new Map()}
        onEnable={vi.fn()}
        onDisable={vi.fn()}
      />,
    )
    expect(screen.getByText('No accounts yet.')).toBeInTheDocument()
  })

  it('renders a distinct empty state when a search/filter excludes every account', () => {
    render(
      <UsersTable
        users={[]}
        personLabels={new Map()}
        onEnable={vi.fn()}
        onDisable={vi.fn()}
        isFiltered
      />,
    )
    expect(screen.getByText('No accounts match your search.')).toBeInTheDocument()
    expect(screen.queryByText('No accounts yet.')).not.toBeInTheDocument()
  })

  it('shows each account with status badge, linked person, and last login', () => {
    render(
      <UsersTable
        users={[
          account({ person_id: 'person-1' }),
          account({
            id: 'user-2',
            display_name: 'Alan Turing',
            email: 'alan@acme.test',
            status: 'disabled',
            person_id: 'person-elsewhere',
            last_login_at: null,
          }),
          account({
            id: 'user-3',
            display_name: 'Grace Hopper',
            email: 'grace@acme.test',
            status: 'invited',
          }),
        ]}
        personLabels={new Map([['person-1', 'Ada L. (staff)']])}
        onEnable={vi.fn()}
        onDisable={vi.fn()}
      />,
    )
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Disabled')).toBeInTheDocument()
    expect(screen.getByText('Invited')).toBeInTheDocument()
    expect(screen.getByText('Ada L. (staff)')).toBeInTheDocument()
    expect(
      screen.getByText('Linked to a person in another organization'),
    ).toBeInTheDocument()
    expect(screen.getByText('Never')).toBeInTheDocument()
  })

  it('enables a disabled account', async () => {
    const onEnable = vi.fn()
    const user = userEvent.setup()
    render(
      <UsersTable
        users={[account({ status: 'disabled' })]}
        personLabels={new Map()}
        onEnable={onEnable}
        onDisable={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Enable' }))
    expect(onEnable).toHaveBeenCalledWith('user-1')
  })

  it('requires inline confirmation before disabling an active account', async () => {
    const onDisable = vi.fn()
    const user = userEvent.setup()
    render(
      <UsersTable
        users={[account()]}
        personLabels={new Map()}
        onEnable={vi.fn()}
        onDisable={onDisable}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Disable' }))
    expect(screen.getByText('Disable this account?')).toBeInTheDocument()
    expect(onDisable).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText('Disable this account?')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Disable' }))
    await user.click(screen.getByRole('button', { name: 'Confirm disable' }))
    expect(onDisable).toHaveBeenCalledWith('user-1')
  })

  it('disables the in-flight row and shows its error verbatim on that row only', async () => {
    const user = userEvent.setup()
    render(
      <UsersTable
        users={[
          account(),
          account({ id: 'user-2', display_name: 'Alan Turing', status: 'disabled' }),
        ]}
        personLabels={new Map()}
        onEnable={vi.fn()}
        onDisable={vi.fn()}
        pendingUserId="user-1"
        actionError={{
          userId: 'user-1',
          message:
            'Cannot disable this user — they are the last remaining active Owner of at least one organization they belong to.',
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Disable' }))
    expect(screen.getByRole('button', { name: 'Disabling…' })).toBeDisabled()
    expect(
      screen.getByText(
        'Cannot disable this user — they are the last remaining active Owner of at least one organization they belong to.',
      ),
    ).toBeInTheDocument()
    // Alan's row (user-2) carries no error.
    expect(screen.getByRole('button', { name: 'Enable' })).toBeEnabled()
  })
})

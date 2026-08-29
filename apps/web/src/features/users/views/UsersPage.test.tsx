import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuth } from '@/features/auth/context/AuthContext'
import { usePeopleLookup } from '@/hooks/usePeople'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import type { Person } from '@/types/entities'
import { UsersPage } from './UsersPage'
import {
  useCreateUser,
  useSetUserStatus,
  useUserAccounts,
} from '../hooks/useUserAccounts'
import type { UserAccount } from '../types/users'

vi.mock('@/features/auth/context/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('@/hooks/usePeople', () => ({ usePeopleLookup: vi.fn() }))
vi.mock('../hooks/useUserAccounts')

const mockedUseAuth = vi.mocked(useAuth)
const mockedUsePeopleLookup = vi.mocked(usePeopleLookup)
const mockedUseUserAccounts = vi.mocked(useUserAccounts)
const mockedUseCreateUser = vi.mocked(useCreateUser)
const mockedUseSetUserStatus = vi.mocked(useSetUserStatus)

function authValue(
  overrides: Partial<ReturnType<typeof useAuth>> = {},
): ReturnType<typeof useAuth> {
  return {
    user: null,
    status: 'authenticated',
    can: (permission: string) => permission === 'user.write',
    canManageResource: () => true,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganization: vi.fn(),
    ...overrides,
  }
}

const IDLE = {
  mutate: vi.fn(),
  mutateAsync: vi.fn().mockResolvedValue(undefined),
  isPending: false,
  isError: false,
  error: null,
  variables: undefined,
}

function mockMutations() {
  mockedUseCreateUser.mockReturnValue({ ...IDLE } as unknown as ReturnType<
    typeof useCreateUser
  >)
  mockedUseSetUserStatus.mockReturnValue({ ...IDLE } as unknown as ReturnType<
    typeof useSetUserStatus
  >)
}

const ACCOUNTS: UserAccount[] = [
  {
    id: 'user-1',
    email: 'ada@acme.test',
    display_name: 'Ada Lovelace',
    status: 'active',
    person_id: null,
    last_login_at: '2026-02-01T09:30:00Z',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'user-2',
    email: 'alan@acme.test',
    display_name: 'Alan Turing',
    status: 'disabled',
    person_id: null,
    last_login_at: null,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
]

describe('UsersPage', () => {
  it('shows a view-only notice for a role without user.write', () => {
    mockedUseAuth.mockReturnValue(authValue({ can: () => false }))
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockMutations()
    mockedUseUserAccounts.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    render(<UsersPage />)

    expect(
      screen.getByText(
        "Your role doesn't include permission to manage user accounts.",
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('User accounts')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Search')).not.toBeInTheDocument()
  })

  it('lists accounts and wires enable to a status:active mutation', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockMutations()
    const setStatus = vi.fn()
    mockedUseSetUserStatus.mockReturnValue({
      ...IDLE,
      mutate: setStatus,
    } as unknown as ReturnType<typeof useSetUserStatus>)
    mockedUseUserAccounts.mockReturnValue(
      mockQuerySuccess({ items: ACCOUNTS, total: 2 }),
    )

    const user = userEvent.setup()
    render(<UsersPage />)

    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument()
    expect(screen.getByText('alan@acme.test')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Enable' }))
    expect(setStatus).toHaveBeenCalledWith({ userId: 'user-2', status: 'active' })
  })

  it('confirms then wires disable to a status:disabled mutation', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockMutations()
    const setStatus = vi.fn()
    mockedUseSetUserStatus.mockReturnValue({
      ...IDLE,
      mutate: setStatus,
    } as unknown as ReturnType<typeof useSetUserStatus>)
    mockedUseUserAccounts.mockReturnValue(
      mockQuerySuccess({ items: ACCOUNTS, total: 2 }),
    )

    const user = userEvent.setup()
    render(<UsersPage />)

    await user.click(screen.getByRole('button', { name: 'Disable' }))
    await user.click(screen.getByRole('button', { name: 'Confirm disable' }))
    expect(setStatus).toHaveBeenCalledWith({ userId: 'user-1', status: 'disabled' })
  })

  it('surfaces the last-Owner rejection from the backend verbatim', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockMutations()
    mockedUseSetUserStatus.mockReturnValue({
      ...IDLE,
      isError: true,
      error: new Error(
        'Cannot disable this user — they are the last remaining active Owner of at least one organization they belong to.',
      ),
      variables: { userId: 'user-1', status: 'disabled' },
    } as unknown as ReturnType<typeof useSetUserStatus>)
    mockedUseUserAccounts.mockReturnValue(
      mockQuerySuccess({ items: ACCOUNTS, total: 2 }),
    )

    render(<UsersPage />)

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Cannot disable this user — they are the last remaining active Owner of at least one organization they belong to.',
    )
  })

  it('offers only unlinked people from the active organization in the create form', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUsePeopleLookup.mockReturnValue(
      new Map<string, Person>([
        ['person-1', { id: 'person-1', display_name: 'Linked Person' } as Person],
        ['person-2', { id: 'person-2', display_name: 'Free Person' } as Person],
      ]),
    )
    mockMutations()
    mockedUseUserAccounts.mockReturnValue(
      mockQuerySuccess({
        items: [{ ...ACCOUNTS[0], person_id: 'person-1' }],
        total: 1,
      }),
    )

    render(<UsersPage />)

    const select = screen.getByLabelText('Linked person (optional)')
    expect(select).toHaveTextContent('Free Person')
    expect(select).not.toHaveTextContent('Linked Person')
  })

  it('renders search and status filter controls for an authorized role', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockMutations()
    mockedUseUserAccounts.mockReturnValue(mockQuerySuccess({ items: ACCOUNTS, total: 2 }))

    render(<UsersPage />)

    expect(screen.getByLabelText('Search')).toBeInTheDocument()
    expect(screen.getByLabelText('Status')).toBeInTheDocument()
  })

  it('debounces the search box before applying it to the accounts query', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockMutations()
    mockedUseUserAccounts.mockReturnValue(mockQuerySuccess({ items: ACCOUNTS, total: 2 }))

    const user = userEvent.setup()
    render(<UsersPage />)

    await user.type(screen.getByLabelText('Search'), 'ada')
    expect(mockedUseUserAccounts).not.toHaveBeenCalledWith({
      q: 'ada',
      status: undefined,
    })

    await waitFor(() => {
      expect(mockedUseUserAccounts).toHaveBeenCalledWith({ q: 'ada', status: undefined })
    })
  })

  it('applies the status filter immediately, without debouncing', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockMutations()
    mockedUseUserAccounts.mockReturnValue(mockQuerySuccess({ items: ACCOUNTS, total: 2 }))

    const user = userEvent.setup()
    render(<UsersPage />)

    await user.selectOptions(screen.getByLabelText('Status'), 'disabled')

    await waitFor(() => {
      expect(mockedUseUserAccounts).toHaveBeenCalledWith({ q: undefined, status: 'disabled' })
    })
  })

  it('clearing the search box restores the unfiltered query', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockMutations()
    mockedUseUserAccounts.mockReturnValue(mockQuerySuccess({ items: ACCOUNTS, total: 2 }))

    const user = userEvent.setup()
    render(<UsersPage />)

    const search = screen.getByLabelText('Search')
    await user.type(search, 'ada')
    await waitFor(() => {
      expect(mockedUseUserAccounts).toHaveBeenCalledWith({ q: 'ada', status: undefined })
    })

    await user.clear(search)
    await waitFor(() => {
      expect(mockedUseUserAccounts).toHaveBeenCalledWith({ q: undefined, status: undefined })
    })
  })

  it('always resolves the create-form Person picker from the unfiltered directory', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockedUsePeopleLookup.mockReturnValue(
      new Map<string, Person>([
        ['person-1', { id: 'person-1', display_name: 'Linked Person' } as Person],
        ['person-2', { id: 'person-2', display_name: 'Free Person' } as Person],
      ]),
    )
    mockMutations()
    // Every call to useUserAccounts (filtered or not) returns the same full
    // set here — this test only asserts the picker still excludes
    // person-1 even while a search term narrows what the table shows.
    mockedUseUserAccounts.mockReturnValue(
      mockQuerySuccess({
        items: [{ ...ACCOUNTS[0], person_id: 'person-1' }, ACCOUNTS[1]],
        total: 2,
      }),
    )

    const user = userEvent.setup()
    render(<UsersPage />)
    await user.type(screen.getByLabelText('Search'), 'alan')

    const select = screen.getByLabelText('Linked person (optional)')
    expect(select).toHaveTextContent('Free Person')
    expect(select).not.toHaveTextContent('Linked Person')
  })
})

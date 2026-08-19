import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useTeams } from '@/hooks/useTeams'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import { TeamAccessSection } from './TeamAccessSection'
import { useUsers } from '../hooks/useUsers'
import {
  useGrantTeamAccess,
  useRevokeTeamAccess,
  useTeamAccessGrants,
} from '../hooks/useTeamAccessGrants'

vi.mock('@/hooks/useTeams')
vi.mock('../hooks/useUsers')
vi.mock('../hooks/useTeamAccessGrants')

const mockedUseTeams = vi.mocked(useTeams)
const mockedUseUsers = vi.mocked(useUsers)
const mockedUseTeamAccessGrants = vi.mocked(useTeamAccessGrants)
const mockedUseGrantTeamAccess = vi.mocked(useGrantTeamAccess)
const mockedUseRevokeTeamAccess = vi.mocked(useRevokeTeamAccess)

const TEAMS = [
  { id: 'team-a', name: 'Design', description: null, created_at: '', updated_at: '' },
  { id: 'team-b', name: 'Engineering', description: null, created_at: '', updated_at: '' },
]

const USERS = [
  { id: 'user-1', email: 'manager@example.com', display_name: 'Manager One', role: 'manager' },
  { id: 'user-2', email: 'manager2@example.com', display_name: 'Manager Two', role: 'manager' },
]

function mockCommonHooks() {
  mockedUseTeams.mockReturnValue(mockQuerySuccess({ items: TEAMS, total: 2 }))
  mockedUseUsers.mockReturnValue(mockQuerySuccess({ items: USERS, total: 2 }))
}

describe('TeamAccessSection', () => {
  it('shows an empty state before a team is selected', () => {
    mockCommonHooks()
    mockedUseTeamAccessGrants.mockReturnValue(mockQuerySuccess([]))
    mockedUseGrantTeamAccess.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof useGrantTeamAccess>)
    mockedUseRevokeTeamAccess.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useRevokeTeamAccess>)

    render(<TeamAccessSection />)
    expect(screen.getByText('Select a team to manage who can edit it.')).toBeInTheDocument()
  })

  it('lets an admin select a team, pick a user, and grant access', async () => {
    mockCommonHooks()
    mockedUseTeamAccessGrants.mockReturnValue(mockQuerySuccess([]))
    const grantMutate = vi.fn()
    mockedUseGrantTeamAccess.mockReturnValue({
      mutate: grantMutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof useGrantTeamAccess>)
    mockedUseRevokeTeamAccess.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useRevokeTeamAccess>)

    const user = userEvent.setup()
    render(<TeamAccessSection />)

    await user.selectOptions(screen.getByLabelText('Team'), 'team-a')
    await user.selectOptions(screen.getByLabelText('User'), 'user-1')

    const grantButton = screen.getByRole('button', { name: 'Grant access' })
    expect(grantButton).toBeEnabled()
    await user.click(grantButton)

    expect(grantMutate).toHaveBeenCalledWith('user-1', expect.anything())
  })

  it('shows existing grants and revokes one on click', async () => {
    mockCommonHooks()
    mockedUseTeamAccessGrants.mockReturnValue(
      mockQuerySuccess([
        {
          id: 'grant-1',
          user_id: 'user-1',
          team_id: 'team-a',
          granted_by_user_id: 'user-2',
          created_at: '2026-01-01T00:00:00Z',
        },
      ]),
    )
    mockedUseGrantTeamAccess.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof useGrantTeamAccess>)
    const revokeMutate = vi.fn()
    mockedUseRevokeTeamAccess.mockReturnValue({
      mutate: revokeMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useRevokeTeamAccess>)

    const user = userEvent.setup()
    render(<TeamAccessSection />)

    await user.selectOptions(screen.getByLabelText('Team'), 'team-a')

    expect(screen.getByText('Manager One (manager@example.com)')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Revoke' }))
    expect(revokeMutate).toHaveBeenCalledWith('user-1')
  })
})

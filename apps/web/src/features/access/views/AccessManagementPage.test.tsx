import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { useAuth } from '@/features/auth/context/AuthContext'
import { useTeams } from '@/hooks/useTeams'
import { useProjects } from '@/hooks/useProjects'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import { AccessManagementPage } from './AccessManagementPage'
import { useUsers } from '../hooks/useUsers'
import {
  useGrantTeamAccess,
  useRevokeTeamAccess,
  useTeamAccessGrants,
} from '../hooks/useTeamAccessGrants'
import {
  useGrantProjectAccess,
  useProjectAccessGrants,
  useRevokeProjectAccess,
} from '../hooks/useProjectAccessGrants'

vi.mock('@/features/auth/context/AuthContext', () => ({
  useAuth: vi.fn(),
}))
vi.mock('@/hooks/useTeams')
vi.mock('@/hooks/useProjects')
vi.mock('../hooks/useUsers')
vi.mock('../hooks/useTeamAccessGrants')
vi.mock('../hooks/useProjectAccessGrants')

const mockedUseAuth = vi.mocked(useAuth)
const mockedUseTeams = vi.mocked(useTeams)
const mockedUseProjects = vi.mocked(useProjects)
const mockedUseUsers = vi.mocked(useUsers)
const mockedUseTeamAccessGrants = vi.mocked(useTeamAccessGrants)
const mockedUseProjectAccessGrants = vi.mocked(useProjectAccessGrants)
const mockedUseGrantTeamAccess = vi.mocked(useGrantTeamAccess)
const mockedUseRevokeTeamAccess = vi.mocked(useRevokeTeamAccess)
const mockedUseGrantProjectAccess = vi.mocked(useGrantProjectAccess)
const mockedUseRevokeProjectAccess = vi.mocked(useRevokeProjectAccess)

describe('AccessManagementPage', () => {
  it('shows a view-only notice for a role without access.manage', () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      status: 'authenticated',
      can: () => false,
      canManageResource: () => false,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganization: vi.fn(),
    })

    render(<AccessManagementPage />)

    expect(
      screen.getByText("Your role doesn't include permission to manage instance-level access."),
    ).toBeInTheDocument()
    expect(screen.queryByText('Team access')).not.toBeInTheDocument()
  })

  it('renders both Team access and Project access sections for Owner/Admin', () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      status: 'authenticated',
      can: () => true,
      canManageResource: () => true,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganization: vi.fn(),
    })
    mockedUseTeams.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseUsers.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseTeamAccessGrants.mockReturnValue(mockQuerySuccess([]))
    mockedUseProjectAccessGrants.mockReturnValue(mockQuerySuccess([]))
    mockedUseGrantTeamAccess.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof useGrantTeamAccess>)
    mockedUseRevokeTeamAccess.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useRevokeTeamAccess>)
    mockedUseGrantProjectAccess.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof useGrantProjectAccess>)
    mockedUseRevokeProjectAccess.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useRevokeProjectAccess>)

    render(<AccessManagementPage />)

    expect(screen.getByText('Team access')).toBeInTheDocument()
    expect(screen.getByText('Project access')).toBeInTheDocument()
  })
})

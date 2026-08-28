import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuth } from '@/features/auth/context/AuthContext'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import type { CurrentUser } from '@/features/auth/types/auth'
import { OrganizationSettingsPage } from './OrganizationSettingsPage'
import { useOrganization, useRenameOrganization } from '../hooks/useOrganization'
import type { Organization } from '../types/organization'

vi.mock('@/features/auth/context/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('../hooks/useOrganization')

const mockedUseAuth = vi.mocked(useAuth)
const mockedUseOrganization = vi.mocked(useOrganization)
const mockedUseRenameOrganization = vi.mocked(useRenameOrganization)

function authValue(
  overrides: Partial<ReturnType<typeof useAuth>> = {},
): ReturnType<typeof useAuth> {
  return {
    user: {
      active_organization: { id: 'org-1', name: 'Acme Corp', slug: 'acme-corp' },
    } as CurrentUser,
    status: 'authenticated',
    can: (permission: string) => permission === 'organization.manage',
    canManageResource: () => true,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganization: vi.fn(),
    ...overrides,
  }
}

const RENAME_IDLE = {
  mutate: vi.fn(),
  mutateAsync: vi.fn().mockResolvedValue(undefined),
  isPending: false,
  isError: false,
  isSuccess: false,
  error: null as Error | null,
}

function mockRename(overrides: Partial<typeof RENAME_IDLE> = {}) {
  mockedUseRenameOrganization.mockReturnValue({
    ...RENAME_IDLE,
    ...overrides,
  } as unknown as ReturnType<typeof useRenameOrganization>)
}

const ORG: Organization = {
  id: 'org-1',
  name: 'Acme Corp',
  slug: 'acme-corp',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('OrganizationSettingsPage', () => {
  it('shows a view-only notice for a non-Owner', () => {
    mockedUseAuth.mockReturnValue(authValue({ can: () => false }))
    mockRename()
    mockedUseOrganization.mockReturnValue(mockQuerySuccess(ORG))

    render(<OrganizationSettingsPage />)

    expect(
      screen.getByText('Only an Owner can view or change organization settings.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Organization settings')).not.toBeInTheDocument()
  })

  it('prompts to select an organization when none is active', () => {
    mockedUseAuth.mockReturnValue(
      authValue({ user: { active_organization: null } as CurrentUser }),
    )
    mockRename()
    mockedUseOrganization.mockReturnValue(mockQuerySuccess(ORG))

    render(<OrganizationSettingsPage />)

    expect(
      screen.getByText('Select an organization to manage its settings.'),
    ).toBeInTheDocument()
  })

  it('renders the name, immutable slug, and status — and no deactivate control', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockRename()
    mockedUseOrganization.mockReturnValue(mockQuerySuccess(ORG))

    render(<OrganizationSettingsPage />)

    expect(screen.getByLabelText('Organization name')).toHaveValue('Acme Corp')
    expect(screen.getByText('acme-corp')).toBeInTheDocument()
    expect(screen.getByText('Cannot be changed')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /deactivate/i }),
    ).not.toBeInTheDocument()
  })

  it('wires the rename form to the mutation', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    const mutateAsync = vi.fn().mockResolvedValue(undefined)
    mockRename({ mutateAsync })
    mockedUseOrganization.mockReturnValue(mockQuerySuccess(ORG))

    const user = userEvent.setup()
    render(<OrganizationSettingsPage />)

    const input = screen.getByLabelText('Organization name')
    await user.clear(input)
    await user.type(input, 'Acme Corporation')
    await user.click(screen.getByRole('button', { name: 'Save name' }))

    expect(mutateAsync).toHaveBeenCalledWith('Acme Corporation')
  })

  it('surfaces a server error from the rename mutation', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockRename({
      isError: true,
      error: new Error('String should have at most 200 characters'),
    })
    mockedUseOrganization.mockReturnValue(mockQuerySuccess(ORG))

    render(<OrganizationSettingsPage />)

    expect(screen.getByRole('alert')).toHaveTextContent(
      'String should have at most 200 characters',
    )
  })
})

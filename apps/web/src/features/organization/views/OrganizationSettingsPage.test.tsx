import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '@/api/client'
import { useAuth } from '@/features/auth/context/AuthContext'
import { mockQueryError, mockQuerySuccess } from '@/test/mockQueryResult'
import type { CurrentUser } from '@/features/auth/types/auth'
import { OrganizationSettingsPage } from './OrganizationSettingsPage'
import {
  useDeactivateOrganization,
  useOrganization,
  useReactivateOrganization,
  useRenameOrganization,
} from '../hooks/useOrganization'
import type { Organization } from '../types/organization'

vi.mock('@/features/auth/context/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('../hooks/useOrganization')

const mockedUseAuth = vi.mocked(useAuth)
const mockedUseOrganization = vi.mocked(useOrganization)
const mockedUseRenameOrganization = vi.mocked(useRenameOrganization)
const mockedUseDeactivateOrganization = vi.mocked(useDeactivateOrganization)
const mockedUseReactivateOrganization = vi.mocked(useReactivateOrganization)

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

const MUTATION_IDLE = {
  mutate: vi.fn(),
  mutateAsync: vi.fn().mockResolvedValue(undefined),
  isPending: false,
  isError: false,
  isSuccess: false,
  error: null as Error | null,
}

function mockRename(overrides: Partial<typeof MUTATION_IDLE> = {}) {
  mockedUseRenameOrganization.mockReturnValue({
    ...MUTATION_IDLE,
    ...overrides,
  } as unknown as ReturnType<typeof useRenameOrganization>)
}
function mockDeactivate(overrides: Partial<typeof MUTATION_IDLE> = {}) {
  mockedUseDeactivateOrganization.mockReturnValue({
    ...MUTATION_IDLE,
    ...overrides,
  } as unknown as ReturnType<typeof useDeactivateOrganization>)
}
function mockReactivate(overrides: Partial<typeof MUTATION_IDLE> = {}) {
  mockedUseReactivateOrganization.mockReturnValue({
    ...MUTATION_IDLE,
    ...overrides,
  } as unknown as ReturnType<typeof useReactivateOrganization>)
}

function mockAllMutationsIdle() {
  mockRename()
  mockDeactivate()
  mockReactivate()
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
  it('shows a view-only notice for a non-Owner and no deactivate control', () => {
    mockedUseAuth.mockReturnValue(authValue({ can: () => false }))
    mockAllMutationsIdle()
    mockedUseOrganization.mockReturnValue(mockQuerySuccess(ORG))

    render(<OrganizationSettingsPage />)

    expect(
      screen.getByText('Only an Owner can view or change organization settings.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Organization settings')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /deactivate/i }),
    ).not.toBeInTheDocument()
  })

  it('prompts to select an organization when none is active', () => {
    mockedUseAuth.mockReturnValue(
      authValue({ user: { active_organization: null } as CurrentUser }),
    )
    mockAllMutationsIdle()
    mockedUseOrganization.mockReturnValue(mockQuerySuccess(ORG))

    render(<OrganizationSettingsPage />)

    expect(
      screen.getByText('Select an organization to manage its settings.'),
    ).toBeInTheDocument()
  })

  it('renders the name, immutable slug, status, and a deactivate control for an Owner', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockAllMutationsIdle()
    mockedUseOrganization.mockReturnValue(mockQuerySuccess(ORG))

    render(<OrganizationSettingsPage />)

    expect(screen.getByLabelText('Organization name')).toHaveValue('Acme Corp')
    expect(screen.getByText('acme-corp')).toBeInTheDocument()
    expect(screen.getByText('Cannot be changed')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Deactivate organization' }),
    ).toBeInTheDocument()
  })

  it('wires the confirmed deactivate to its mutation', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockRename()
    mockReactivate()
    const deactivateMutate = vi.fn()
    mockDeactivate({ mutate: deactivateMutate })
    mockedUseOrganization.mockReturnValue(mockQuerySuccess(ORG))

    const user = userEvent.setup()
    render(<OrganizationSettingsPage />)

    await user.click(screen.getByRole('button', { name: 'Deactivate organization' }))
    await user.click(screen.getByRole('button', { name: 'Confirm deactivate' }))
    expect(deactivateMutate).toHaveBeenCalledTimes(1)
  })

  it('surfaces the >=2-Owner 422 from the deactivate guard without reporting success', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockRename()
    mockReactivate()
    mockDeactivate({
      isError: true,
      error: new ApiError(
        422,
        'This organization cannot be deactivated while it has only one active Owner — deactivation would leave no one able to reactivate it. Add a second Owner first, then try again.',
      ),
    })
    mockedUseOrganization.mockReturnValue(mockQuerySuccess(ORG))

    render(<OrganizationSettingsPage />)

    expect(screen.getByRole('alert')).toHaveTextContent(
      'This organization cannot be deactivated while it has only one active Owner',
    )
  })

  it('renders the recovery panel when the organization is inactive (409 from GET)', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockAllMutationsIdle()
    mockedUseOrganization.mockReturnValue(
      mockQueryError(new ApiError(409, 'This organization is no longer active.')),
    )

    render(<OrganizationSettingsPage />)

    expect(screen.getByText('This organization is inactive')).toBeInTheDocument()
    expect(screen.getByText('Acme Corp has been deactivated.')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Reactivate organization' }),
    ).toBeInTheDocument()
    // the settings form is not rendered in the recovery state
    expect(screen.queryByLabelText('Organization name')).not.toBeInTheDocument()
  })

  it('wires the reactivate button to its mutation', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockRename()
    mockDeactivate()
    const reactivateMutate = vi.fn()
    mockReactivate({ mutate: reactivateMutate })
    mockedUseOrganization.mockReturnValue(
      mockQueryError(new ApiError(409, 'This organization is no longer active.')),
    )

    const user = userEvent.setup()
    render(<OrganizationSettingsPage />)

    await user.click(screen.getByRole('button', { name: 'Reactivate organization' }))
    expect(reactivateMutate).toHaveBeenCalledTimes(1)
  })

  it('surfaces a reactivation error verbatim', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockRename()
    mockDeactivate()
    mockReactivate({
      isError: true,
      error: new ApiError(403, 'Only an Owner can reactivate an organization.'),
    })
    mockedUseOrganization.mockReturnValue(
      mockQueryError(new ApiError(409, 'This organization is no longer active.')),
    )

    render(<OrganizationSettingsPage />)

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Only an Owner can reactivate an organization.',
    )
  })

  it('shows a generic error state (not the recovery panel) for a non-409 GET failure', () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockAllMutationsIdle()
    mockedUseOrganization.mockReturnValue(
      mockQueryError(new ApiError(500, 'The database is temporarily unavailable.')),
    )

    render(<OrganizationSettingsPage />)

    expect(
      screen.queryByText('This organization is inactive'),
    ).not.toBeInTheDocument()
    expect(
      screen.getByText('The database is temporarily unavailable.'),
    ).toBeInTheDocument()
  })

  it('wires the rename form to its mutation', async () => {
    mockedUseAuth.mockReturnValue(authValue())
    mockDeactivate()
    mockReactivate()
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
})

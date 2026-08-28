import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { makeCurrentUser } from '@/test/fixtures'
import { SelectOrganizationPage } from './SelectOrganizationPage'
import { organizationsApi } from '../api/organizationsApi'
import { useAuth } from '../context/AuthContext'

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))
vi.mock('../api/organizationsApi')

const mockUseAuth = vi.mocked(useAuth)
const mockedOrganizationsApi = vi.mocked(organizationsApi)

function mockAuth(overrides: Partial<ReturnType<typeof useAuth>> = {}) {
  mockUseAuth.mockReturnValue({
    user: makeCurrentUser({ active_organization: null, role: null, organizations: [] }),
    status: 'no-organization',
    can: () => false,
    canManageResource: () => false,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganization: vi.fn(),
    ...overrides,
  })
}

describe('SelectOrganizationPage', () => {
  it('lists every organization the account belongs to', () => {
    mockAuth({
      user: makeCurrentUser({
        active_organization: null,
        role: null,
        organizations: [
          { id: 'org-1', name: 'Org One', slug: 'org-one', is_active: true },
          { id: 'org-2', name: 'Org Two', slug: 'org-two', is_active: true },
        ],
      }),
    })
    render(
      <MemoryRouter>
        <SelectOrganizationPage />
      </MemoryRouter>,
    )
    expect(screen.getByRole('button', { name: 'Org One' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Org Two' })).toBeInTheDocument()
  })

  it('does not offer a deactivated organization as a selectable choice (Phase 33)', () => {
    mockAuth({
      user: makeCurrentUser({
        active_organization: null,
        role: null,
        organizations: [
          { id: 'org-1', name: 'Org One', slug: 'org-one', is_active: true },
          { id: 'org-2', name: 'Deactivated Org', slug: 'gone', is_active: false },
        ],
      }),
    })
    render(
      <MemoryRouter>
        <SelectOrganizationPage />
      </MemoryRouter>,
    )
    expect(screen.getByRole('button', { name: 'Org One' })).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Deactivated Org' }),
    ).not.toBeInTheDocument()
  })

  it('hides the selection list entirely when every membership organization is inactive', () => {
    mockAuth({
      user: makeCurrentUser({
        active_organization: null,
        role: null,
        organizations: [
          { id: 'org-1', name: 'Gone One', slug: 'gone-one', is_active: false },
        ],
      }),
    })
    render(
      <MemoryRouter>
        <SelectOrganizationPage />
      </MemoryRouter>,
    )
    expect(screen.queryByText('Select an organization')).not.toBeInTheDocument()
    expect(screen.getByText('Create an organization')).toBeInTheDocument()
  })

  it('does not show an organization list for an account with none yet', () => {
    mockAuth()
    render(
      <MemoryRouter>
        <SelectOrganizationPage />
      </MemoryRouter>,
    )
    expect(screen.queryByText('Select an organization')).not.toBeInTheDocument()
    expect(screen.getByText('Create an organization')).toBeInTheDocument()
  })

  it('switches into the selected organization when clicked', async () => {
    const switchOrganization = vi.fn().mockResolvedValue(undefined)
    mockAuth({
      user: makeCurrentUser({
        active_organization: null,
        role: null,
        organizations: [{ id: 'org-1', name: 'Org One', slug: 'org-one', is_active: true }],
      }),
      switchOrganization,
    })
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <SelectOrganizationPage />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'Org One' }))

    expect(switchOrganization).toHaveBeenCalledWith('org-1')
  })

  it('creates a new organization and switches into it', async () => {
    const switchOrganization = vi.fn().mockResolvedValue(undefined)
    mockAuth({ switchOrganization })
    mockedOrganizationsApi.create.mockResolvedValue({
      id: 'org-new',
      name: 'Acme Inc',
      slug: 'acme-inc',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <SelectOrganizationPage />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText('Name'), 'Acme Inc')
    await user.type(screen.getByLabelText('Slug'), 'acme-inc')
    await user.click(screen.getByRole('button', { name: 'Create organization' }))

    expect(mockedOrganizationsApi.create).toHaveBeenCalledWith({
      name: 'Acme Inc',
      slug: 'acme-inc',
    })
    expect(switchOrganization).toHaveBeenCalledWith('org-new')
  })

  it('shows the backend error message when creation fails', async () => {
    mockAuth()
    mockedOrganizationsApi.create.mockRejectedValue(
      new ApiError(409, "An organization with slug 'acme-inc' already exists."),
    )
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <SelectOrganizationPage />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText('Name'), 'Acme Inc')
    await user.type(screen.getByLabelText('Slug'), 'acme-inc')
    await user.click(screen.getByRole('button', { name: 'Create organization' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "An organization with slug 'acme-inc' already exists.",
    )
  })

  it('redirects away when already authenticated with an active organization', () => {
    mockAuth({ user: makeCurrentUser(), status: 'authenticated' })
    render(
      <MemoryRouter initialEntries={['/select-organization']}>
        <Routes>
          <Route path="/select-organization" element={<SelectOrganizationPage />} />
          <Route path="/" element={<div>Protected home</div>} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('Protected home')).toBeInTheDocument()
  })
})

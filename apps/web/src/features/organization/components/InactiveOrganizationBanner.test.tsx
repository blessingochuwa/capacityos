import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useAuth } from '@/features/auth/context/AuthContext'
import type { CurrentUser } from '@/features/auth/types/auth'
import { InactiveOrganizationBanner } from './InactiveOrganizationBanner'

vi.mock('@/features/auth/context/AuthContext', () => ({ useAuth: vi.fn() }))
const mockedUseAuth = vi.mocked(useAuth)

function authValue(
  overrides: Partial<ReturnType<typeof useAuth>> = {},
): ReturnType<typeof useAuth> {
  return {
    user: {
      active_organization: {
        id: 'org-1',
        name: 'Acme Corp',
        slug: 'acme-corp',
        is_active: true,
      },
    } as CurrentUser,
    status: 'authenticated',
    can: () => false,
    canManageResource: () => true,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganization: vi.fn(),
    ...overrides,
  }
}

function renderBanner() {
  render(
    <MemoryRouter>
      <InactiveOrganizationBanner />
    </MemoryRouter>,
  )
}

describe('InactiveOrganizationBanner', () => {
  it('renders nothing while the active organization is active', () => {
    mockedUseAuth.mockReturnValue(authValue())
    const { container } = render(
      <MemoryRouter>
        <InactiveOrganizationBanner />
      </MemoryRouter>,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when there is no active organization', () => {
    mockedUseAuth.mockReturnValue(
      authValue({ user: { active_organization: null } as CurrentUser }),
    )
    const { container } = render(
      <MemoryRouter>
        <InactiveOrganizationBanner />
      </MemoryRouter>,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('shows an alert naming the inactive organization', () => {
    mockedUseAuth.mockReturnValue(
      authValue({
        user: {
          active_organization: {
            id: 'org-1',
            name: 'Acme Corp',
            slug: 'acme-corp',
            is_active: false,
          },
        } as CurrentUser,
      }),
    )
    renderBanner()
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('This organization is inactive.')
    expect(alert).toHaveTextContent('Acme Corp has been deactivated')
  })

  it('gives an Owner a link to the existing recovery surface', () => {
    mockedUseAuth.mockReturnValue(
      authValue({
        can: (permission: string) => permission === 'organization.manage',
        user: {
          active_organization: {
            id: 'org-1',
            name: 'Acme Corp',
            slug: 'acme-corp',
            is_active: false,
          },
        } as CurrentUser,
      }),
    )
    renderBanner()
    const link = screen.getByRole('link', {
      name: 'Go to organization settings to reactivate it',
    })
    expect(link).toHaveAttribute('href', '/admin/organization')
  })

  it('gives a non-Owner guidance but no reactivation action', () => {
    mockedUseAuth.mockReturnValue(
      authValue({
        can: () => false,
        user: {
          active_organization: {
            id: 'org-1',
            name: 'Acme Corp',
            slug: 'acme-corp',
            is_active: false,
          },
        } as CurrentUser,
      }),
    )
    renderBanner()
    expect(
      screen.getByText('Ask an organization Owner to reactivate it.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})

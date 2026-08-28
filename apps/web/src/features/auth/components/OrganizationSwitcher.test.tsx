import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuth } from '../context/AuthContext'
import type { CurrentUser } from '../types/auth'
import { OrganizationSwitcher } from './OrganizationSwitcher'

vi.mock('../context/AuthContext', () => ({ useAuth: vi.fn() }))
const mockedUseAuth = vi.mocked(useAuth)

function authValue(
  user: Partial<CurrentUser> | null,
  switchOrganization = vi.fn().mockResolvedValue(undefined),
): ReturnType<typeof useAuth> {
  return {
    user: user as CurrentUser | null,
    status: 'authenticated',
    can: () => false,
    canManageResource: () => true,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganization,
  }
}

const ORG = (id: string, name: string, is_active = true) => ({
  id,
  name,
  slug: id,
  is_active,
})

describe('OrganizationSwitcher', () => {
  it('renders nothing when the caller has one active organization', () => {
    mockedUseAuth.mockReturnValue(
      authValue({
        active_organization: ORG('org-1', 'Org One'),
        organizations: [ORG('org-1', 'Org One')],
      }),
    )
    const { container } = render(<OrganizationSwitcher />)
    expect(container).toBeEmptyDOMElement()
  })

  it('offers the active organizations and omits an inactive one the caller is not in', () => {
    mockedUseAuth.mockReturnValue(
      authValue({
        active_organization: ORG('org-1', 'Org One'),
        organizations: [
          ORG('org-1', 'Org One'),
          ORG('org-2', 'Org Two'),
          ORG('org-3', 'Deactivated Org', false),
        ],
      }),
    )
    render(<OrganizationSwitcher />)
    const select = screen.getByLabelText('Organization')
    expect(select).toHaveTextContent('Org One')
    expect(select).toHaveTextContent('Org Two')
    expect(select).not.toHaveTextContent('Deactivated Org')
  })

  it('keeps the current organization visible and labelled when it is itself inactive', () => {
    mockedUseAuth.mockReturnValue(
      authValue({
        active_organization: ORG('org-1', 'Org One', false),
        organizations: [ORG('org-1', 'Org One', false), ORG('org-2', 'Org Two')],
      }),
    )
    render(<OrganizationSwitcher />)
    const select = screen.getByLabelText('Organization')
    expect(select).toHaveValue('org-1')
    expect(select).toHaveTextContent('Org One (inactive)')
    expect(select).toHaveTextContent('Org Two')
  })

  it('renders nothing when the only other organizations are inactive', () => {
    mockedUseAuth.mockReturnValue(
      authValue({
        active_organization: ORG('org-1', 'Org One'),
        organizations: [ORG('org-1', 'Org One'), ORG('org-2', 'Gone', false)],
      }),
    )
    const { container } = render(<OrganizationSwitcher />)
    expect(container).toBeEmptyDOMElement()
  })

  it('still switches into a chosen active organization', async () => {
    const switchOrganization = vi.fn().mockResolvedValue(undefined)
    mockedUseAuth.mockReturnValue(
      authValue(
        {
          active_organization: ORG('org-1', 'Org One'),
          organizations: [ORG('org-1', 'Org One'), ORG('org-2', 'Org Two')],
        },
        switchOrganization,
      ),
    )
    const user = userEvent.setup()
    render(<OrganizationSwitcher />)
    await user.selectOptions(screen.getByLabelText('Organization'), 'org-2')
    expect(switchOrganization).toHaveBeenCalledWith('org-2')
  })
})

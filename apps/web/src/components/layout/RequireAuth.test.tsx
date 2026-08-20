import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { makeCurrentUser } from '@/test/fixtures'
import { useAuth } from '@/features/auth/context/AuthContext'
import { RequireAuth } from './RequireAuth'

vi.mock('@/features/auth/context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

const mockUseAuth = vi.mocked(useAuth)

function renderProtected() {
  render(
    <MemoryRouter initialEntries={['/capacity']}>
      <Routes>
        <Route path="/login" element={<div>Login page</div>} />
        <Route
          path="/select-organization"
          element={<div>Select organization page</div>}
        />
        <Route
          path="/capacity"
          element={
            <RequireAuth>
              <div>Protected content</div>
            </RequireAuth>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RequireAuth', () => {
  it('shows a loading state while the session is being checked', () => {
    mockUseAuth.mockReturnValue({
      user: null,
      status: 'loading',
      can: () => false,
      canManageResource: () => false,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganization: vi.fn(),
    })
    renderProtected()
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
  })

  it('redirects to /login when unauthenticated', () => {
    mockUseAuth.mockReturnValue({
      user: null,
      status: 'unauthenticated',
      can: () => false,
      canManageResource: () => false,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganization: vi.fn(),
    })
    renderProtected()
    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
  })

  it('redirects to /select-organization when authenticated with no active organization', () => {
    mockUseAuth.mockReturnValue({
      user: makeCurrentUser({ active_organization: null }),
      status: 'no-organization',
      can: () => false,
      canManageResource: () => false,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganization: vi.fn(),
    })
    renderProtected()
    expect(screen.getByText('Select organization page')).toBeInTheDocument()
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
  })

  it('renders the protected content when authenticated', () => {
    mockUseAuth.mockReturnValue({
      user: makeCurrentUser(),
      status: 'authenticated',
      can: () => true,
      canManageResource: () => true,
      login: vi.fn(),
      logout: vi.fn(),
      switchOrganization: vi.fn(),
    })
    renderProtected()
    expect(screen.getByText('Protected content')).toBeInTheDocument()
  })
})

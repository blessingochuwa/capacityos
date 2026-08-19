import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { makeCurrentUser } from '@/test/fixtures'
import { LoginPage } from './LoginPage'
import { useAuth } from '../context/AuthContext'

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

const mockUseAuth = vi.mocked(useAuth)

function mockAuth(overrides: Partial<ReturnType<typeof useAuth>> = {}) {
  mockUseAuth.mockReturnValue({
    user: null,
    status: 'unauthenticated',
    can: () => false,
    canManageResource: () => false,
    login: vi.fn(),
    logout: vi.fn(),
    ...overrides,
  })
}

describe('LoginPage', () => {
  it('renders email and password fields', () => {
    mockAuth()
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('calls login with the entered credentials on submit', async () => {
    const login = vi.fn().mockResolvedValue(undefined)
    mockAuth({ login })
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText('Email'), 'owner@example.com')
    await user.type(screen.getByLabelText('Password'), 'a-strong-password')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(login).toHaveBeenCalledWith({
      email: 'owner@example.com',
      password: 'a-strong-password',
    })
  })

  it('shows the backend error message when login fails', async () => {
    const login = vi
      .fn()
      .mockRejectedValue(new ApiError(401, 'Invalid email or password.'))
    mockAuth({ login })
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText('Email'), 'owner@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Invalid email or password.',
    )
  })

  it('redirects away from /login when already authenticated', () => {
    mockAuth({ user: makeCurrentUser(), status: 'authenticated' })
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Protected home</div>} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('Protected home')).toBeInTheDocument()
  })
})

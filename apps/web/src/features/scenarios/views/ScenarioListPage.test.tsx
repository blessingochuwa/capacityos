import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ScenarioListPage } from './ScenarioListPage'
import { useScenarios } from '../hooks/useScenarios'
import { useCreateScenario } from '../hooks/useScenarioMutations'
import {
  mockQueryError,
  mockQueryPending,
  mockQuerySuccess,
} from '@/test/mockQueryResult'
import { makeScenario } from '@/test/fixtures'
import { useAuth } from '@/features/auth/context/AuthContext'

vi.mock('../hooks/useScenarios')
vi.mock('../hooks/useScenarioMutations')
// Owner-equivalent permissions by default, matching every pre-Phase-10 test's
// implicit assumption of full access — see apps/api/tests/conftest.py's
// identical "client fixture defaults to Owner" reasoning.
vi.mock('@/features/auth/context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

const mockedUseScenarios = vi.mocked(useScenarios)
const mockedUseCreateScenario = vi.mocked(useCreateScenario)
const mockedUseAuth = vi.mocked(useAuth)

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/scenarios']}>
      <ScenarioListPage />
    </MemoryRouter>,
  )
}

describe('ScenarioListPage', () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue({
      user: null,
      status: 'authenticated',
      can: () => true,
      canManageResource: () => true,
      login: vi.fn(),
      logout: vi.fn(),
    })
  })

  it('renders a loading state while scenarios are being fetched', () => {
    mockedUseScenarios.mockReturnValue(mockQueryPending())
    mockedUseCreateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateScenario>)

    renderPage()

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders an empty state when there are no scenarios', () => {
    mockedUseScenarios.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )
    mockedUseCreateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateScenario>)

    renderPage()

    expect(screen.getByText('No scenarios yet.')).toBeInTheDocument()
  })

  it('lists scenarios with their name and status', () => {
    mockedUseScenarios.mockReturnValue(
      mockQuerySuccess({
        items: [
          makeScenario({
            id: 'scenario-1',
            name: 'Launch earlier',
            status: 'active',
          }),
        ],
        total: 1,
      }),
    )
    mockedUseCreateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateScenario>)

    renderPage()

    expect(
      screen.getByRole('link', { name: 'Launch earlier' }),
    ).toHaveAttribute('href', '/scenarios/scenario-1')
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('renders an error state with a retry action when scenarios fail to load', () => {
    mockedUseScenarios.mockReturnValue(mockQueryError())
    mockedUseCreateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateScenario>)

    renderPage()

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('hides the create-scenario form for a role without scenario.write (Phase 10)', () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      status: 'authenticated',
      can: () => false,
      canManageResource: () => false,
      login: vi.fn(),
      logout: vi.fn(),
    })
    mockedUseScenarios.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )
    mockedUseCreateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCreateScenario>)

    renderPage()

    expect(
      screen.queryByRole('button', { name: 'Create scenario' }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByText(/can view scenarios but not create/i),
    ).toBeInTheDocument()
  })
})

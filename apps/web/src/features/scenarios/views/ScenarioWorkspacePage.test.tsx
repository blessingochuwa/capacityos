import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ScenarioWorkspacePage } from './ScenarioWorkspacePage'
import { useScenario } from '../hooks/useScenario'
import { useScenarioOperations } from '../hooks/useScenarioOperations'
import { useScenarioComparison } from '../hooks/useScenarioComparison'
import { useCalculateScenario } from '../hooks/useCalculateScenario'
import {
  useDeleteScenario,
  useUpdateScenario,
} from '../hooks/useScenarioMutations'
import {
  useCreateScenarioOperation,
  useDeleteScenarioOperation,
} from '../hooks/useScenarioOperationMutations'
import { usePeople, usePeopleLookup } from '@/hooks/usePeople'
import { useProjects, useProjectsLookup } from '@/hooks/useProjects'
import { useScenarioSignals } from '@/features/insights/hooks/useScenarioSignals'
import { useFrameworks } from '@/features/prioritization/hooks/useFrameworks'
import { useScenarioPriorityComparison } from '../hooks/useScenarioPriorityComparison'
import { useScenarioPriorityOverrides } from '../hooks/useScenarioPriorityOverrides'
import {
  mockQueryError,
  mockQueryPending,
  mockQuerySuccess,
} from '@/test/mockQueryResult'
import {
  makePerson,
  makePrioritizationFramework,
  makeProject,
  makeScenario,
  makeScenarioComparison,
  makeScenarioOperation,
  makeScenarioPriorityComparison,
  makeScenarioPriorityOverride,
  makeSignal,
} from '@/test/fixtures'

vi.mock('../hooks/useScenario')
vi.mock('../hooks/useScenarioOperations')
vi.mock('../hooks/useScenarioComparison')
vi.mock('../hooks/useCalculateScenario')
vi.mock('../hooks/useScenarioMutations')
vi.mock('../hooks/useScenarioOperationMutations')
vi.mock('../hooks/useScenarioPriorityComparison')
vi.mock('../hooks/useScenarioPriorityOverrides')
vi.mock('@/hooks/usePeople')
vi.mock('@/hooks/useProjects')
vi.mock('@/features/insights/hooks/useScenarioSignals')
vi.mock('@/features/prioritization/hooks/useFrameworks')

const mockedUseScenario = vi.mocked(useScenario)
const mockedUseScenarioOperations = vi.mocked(useScenarioOperations)
const mockedUseScenarioComparison = vi.mocked(useScenarioComparison)
const mockedUseCalculateScenario = vi.mocked(useCalculateScenario)
const mockedUseUpdateScenario = vi.mocked(useUpdateScenario)
const mockedUseDeleteScenario = vi.mocked(useDeleteScenario)
const mockedUseDeleteScenarioOperation = vi.mocked(useDeleteScenarioOperation)
const mockedUseCreateScenarioOperation = vi.mocked(useCreateScenarioOperation)
const mockedUsePeople = vi.mocked(usePeople)
const mockedUsePeopleLookup = vi.mocked(usePeopleLookup)
const mockedUseProjects = vi.mocked(useProjects)
const mockedUseProjectsLookup = vi.mocked(useProjectsLookup)
const mockedUseScenarioSignals = vi.mocked(useScenarioSignals)
const mockedUseFrameworks = vi.mocked(useFrameworks)
const mockedUseScenarioPriorityOverrides = vi.mocked(useScenarioPriorityOverrides)
const mockedUseScenarioPriorityComparison = vi.mocked(useScenarioPriorityComparison)

function mockCommonHooks() {
  mockedUseUpdateScenario.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof useUpdateScenario>)
  mockedUseDeleteScenario.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof useDeleteScenario>)
  mockedUseDeleteScenarioOperation.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    variables: undefined,
  } as unknown as ReturnType<typeof useDeleteScenarioOperation>)
  mockedUseCreateScenarioOperation.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof useCreateScenarioOperation>)
  mockedUsePeople.mockReturnValue(
    mockQuerySuccess({ items: [makePerson()], total: 1 }),
  )
  mockedUsePeopleLookup.mockReturnValue(
    new Map([['person-1', makePerson({ id: 'person-1' })]]),
  )
  mockedUseProjects.mockReturnValue(
    mockQuerySuccess({ items: [makeProject()], total: 1 }),
  )
  mockedUseProjectsLookup.mockReturnValue(
    new Map([['project-1', makeProject({ id: 'project-1' })]]),
  )
  mockedUseScenarioSignals.mockReturnValue(mockQueryPending())
  mockedUseFrameworks.mockReturnValue(
    mockQuerySuccess({ items: [makePrioritizationFramework()], total: 1 }),
  )
  mockedUseScenarioPriorityOverrides.mockReturnValue(mockQuerySuccess([]))
  mockedUseScenarioPriorityComparison.mockReturnValue(mockQueryPending())
}

function renderPage() {
  // AddChangeForm renders unmocked and calls usePersonAllocations
  // (real react-query hook) once a person is selected — not exercised by
  // these tests, but it still needs a QueryClient in the tree to mount.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/scenarios/scenario-1']}>
        <Routes>
          <Route
            path="/scenarios/:scenarioId"
            element={<ScenarioWorkspacePage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ScenarioWorkspacePage', () => {
  it('renders a loading state while the scenario is being fetched', () => {
    mockCommonHooks()
    mockedUseScenario.mockReturnValue(mockQueryPending())
    mockedUseScenarioOperations.mockReturnValue(mockQueryPending())
    mockedUseScenarioComparison.mockReturnValue(mockQueryPending())
    mockedUseCalculateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCalculateScenario>)

    renderPage()

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders an error state when the scenario fails to load', () => {
    mockCommonHooks()
    mockedUseScenario.mockReturnValue(mockQueryError())
    mockedUseScenarioOperations.mockReturnValue(mockQueryPending())
    mockedUseScenarioComparison.mockReturnValue(mockQueryPending())
    mockedUseCalculateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCalculateScenario>)

    renderPage()

    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('shows the what-if banner and an empty change list when there are no operations', () => {
    mockCommonHooks()
    mockedUseScenario.mockReturnValue(mockQuerySuccess(makeScenario()))
    mockedUseScenarioOperations.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )
    mockedUseScenarioComparison.mockReturnValue(mockQueryPending())
    mockedUseCalculateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCalculateScenario>)

    renderPage()

    expect(
      screen.getByText(/does not change your current plan/),
    ).toBeInTheDocument()
    expect(screen.getByText('No changes yet.')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Add a change and click Calculate to see baseline vs scenario capacity.',
      ),
    ).toBeInTheDocument()
  })

  it('renders comparison, risks, and impact once a calculation has completed', () => {
    mockCommonHooks()
    mockedUseScenario.mockReturnValue(mockQuerySuccess(makeScenario()))
    mockedUseScenarioOperations.mockReturnValue(
      mockQuerySuccess({ items: [makeScenarioOperation()], total: 1 }),
    )
    mockedUseScenarioComparison.mockReturnValue(
      mockQuerySuccess(makeScenarioComparison()),
    )
    // Simulates a calculate mutation that has already succeeded — the
    // workspace derives hasCalculatedOnce from calculate.isSuccess (not
    // from a callback passed to .mutate(), which doesn't survive React
    // StrictMode's double-invocation of the auto-calculate effect in
    // development — see ScenarioWorkspacePage's comment on that effect).
    mockedUseCalculateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isSuccess: true,
    } as unknown as ReturnType<typeof useCalculateScenario>)
    mockedUseScenarioSignals.mockReturnValue(
      mockQuerySuccess({
        items: [makeSignal({ entity_label: 'Jane Doe' })],
        total: 1,
      }),
    )

    renderPage()

    expect(screen.getByText('Baseline vs scenario')).toBeInTheDocument()
    expect(screen.getByText('Utilization')).toBeInTheDocument()
    expect(screen.getByText('People affected')).toBeInTheDocument()
    expect(screen.getByText('Operational signals')).toBeInTheDocument()
    expect(
      screen.getByText(/Jane Doe is allocated 6.00h more/),
    ).toBeInTheDocument()
  })

  it('renders the priority overrides section with its empty state', () => {
    mockCommonHooks()
    mockedUseScenario.mockReturnValue(mockQuerySuccess(makeScenario()))
    mockedUseScenarioOperations.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )
    mockedUseScenarioComparison.mockReturnValue(mockQueryPending())
    mockedUseCalculateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCalculateScenario>)

    renderPage()

    expect(screen.getByText('Priority overrides')).toBeInTheDocument()
    expect(
      screen.getByText(/No hypothetical prioritization values recorded/),
    ).toBeInTheDocument()
    expect(screen.getByText('Priority comparison')).toBeInTheDocument()
    expect(
      screen.getByText('Select a framework above to see the comparison.'),
    ).toBeInTheDocument()
  })

  it('shows the baseline-vs-scenario comparison once a framework is selected', async () => {
    mockCommonHooks()
    mockedUseScenario.mockReturnValue(mockQuerySuccess(makeScenario()))
    mockedUseScenarioOperations.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )
    mockedUseScenarioComparison.mockReturnValue(mockQueryPending())
    mockedUseCalculateScenario.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCalculateScenario>)
    mockedUseScenarioPriorityOverrides.mockReturnValue(
      mockQuerySuccess([makeScenarioPriorityOverride()]),
    )
    mockedUseScenarioPriorityComparison.mockReturnValue(
      mockQuerySuccess(makeScenarioPriorityComparison()),
    )

    renderPage()
    const user = userEvent.setup()
    await user.selectOptions(screen.getByLabelText('Comparison framework'), 'framework-1')

    expect(
      screen.getByText('This scenario changes prioritization under this framework.'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('Website Redesign').length).toBeGreaterThan(0)
  })
})

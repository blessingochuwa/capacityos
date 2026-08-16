import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { InsightsOverviewPage } from './InsightsOverviewPage'
import { useTeams } from '@/hooks/useTeams'
import { useProjects } from '@/hooks/useProjects'
import { useScenarios } from '@/features/scenarios/hooks/useScenarios'
import { useTeamSummary } from '../hooks/useTeamSummary'
import { useTeamSignals } from '../hooks/useTeamSignals'
import { useProjectSignals } from '../hooks/useProjectSignals'
import { useScenarioSignals } from '../hooks/useScenarioSignals'
import {
  mockQueryError,
  mockQueryPending,
  mockQuerySuccess,
} from '@/test/mockQueryResult'
import { makeInsightsSummary, makeSignal, makeTeam } from '@/test/fixtures'

vi.mock('@/hooks/useTeams')
vi.mock('@/hooks/useProjects')
vi.mock('@/features/scenarios/hooks/useScenarios')
vi.mock('../hooks/useTeamSummary')
vi.mock('../hooks/useTeamSignals')
vi.mock('../hooks/useProjectSignals')
vi.mock('../hooks/useScenarioSignals')

const mockedUseTeams = vi.mocked(useTeams)
const mockedUseProjects = vi.mocked(useProjects)
const mockedUseScenarios = vi.mocked(useScenarios)
const mockedUseTeamSummary = vi.mocked(useTeamSummary)
const mockedUseTeamSignals = vi.mocked(useTeamSignals)
const mockedUseProjectSignals = vi.mocked(useProjectSignals)
const mockedUseScenarioSignals = vi.mocked(useScenarioSignals)

function mockPickerHooks() {
  mockedUseTeams.mockReturnValue(
    mockQuerySuccess({
      items: [makeTeam({ id: 'team-1', name: 'Product Design' })],
      total: 1,
    }),
  )
  mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
  mockedUseScenarios.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
  mockedUseProjectSignals.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
  mockedUseScenarioSignals.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
}

function renderPage(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <InsightsOverviewPage />
    </MemoryRouter>,
  )
}

describe('InsightsOverviewPage', () => {
  it('prompts for a team when none is selected', () => {
    mockedUseTeams.mockReturnValue(
      mockQuerySuccess({
        items: [makeTeam({ id: 'team-1' }), makeTeam({ id: 'team-2' })],
        total: 2,
      }),
    )
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseScenarios.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseTeamSummary.mockReturnValue(mockQueryPending())
    mockedUseTeamSignals.mockReturnValue(mockQueryPending())
    mockedUseProjectSignals.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    mockedUseScenarioSignals.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    renderPage('/insights')

    expect(
      screen.getByText('Select a team to view operational insights.'),
    ).toBeInTheDocument()
  })

  it('renders a healthy, reassuring empty state when there are no signals', () => {
    mockPickerHooks()
    mockedUseTeamSummary.mockReturnValue(
      mockQuerySuccess(makeInsightsSummary()),
    )
    mockedUseTeamSignals.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    renderPage('/insights?team=team-1')

    expect(
      screen.getByText('No signals — this team is healthy for this period.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Critical signals')).toBeInTheDocument()
  })

  it('renders a critical signal with its severity, label, and explanation', () => {
    mockPickerHooks()
    const signal = makeSignal({ entity_label: 'Jane Doe' })
    mockedUseTeamSummary.mockReturnValue(
      mockQuerySuccess(
        makeInsightsSummary({
          signal_counts: { critical: 1, warning: 0, info: 0 },
        }),
      ),
    )
    mockedUseTeamSignals.mockReturnValue(
      mockQuerySuccess({ items: [signal], total: 1 }),
    )

    renderPage('/insights?team=team-1')

    expect(screen.getByText('Critical')).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.getByText(signal.explanation)).toBeInTheDocument()
  })

  it('shows the signal detail panel when a row is selected', async () => {
    mockPickerHooks()
    const signal = makeSignal({ entity_label: 'Jane Doe' })
    mockedUseTeamSummary.mockReturnValue(
      mockQuerySuccess(
        makeInsightsSummary({
          signal_counts: { critical: 1, warning: 0, info: 0 },
        }),
      ),
    )
    mockedUseTeamSignals.mockReturnValue(
      mockQuerySuccess({ items: [signal], total: 1 }),
    )

    const user = userEvent.setup()
    renderPage('/insights?team=team-1')

    await user.click(screen.getByRole('button', { name: /Jane Doe/ }))
    expect(screen.getByText('Over-allocated')).toBeInTheDocument()
  })

  it('renders an error state when the team summary fails to load', () => {
    mockPickerHooks()
    mockedUseTeamSummary.mockReturnValue(mockQueryError())
    mockedUseTeamSignals.mockReturnValue(mockQueryPending())

    renderPage('/insights?team=team-1')

    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})

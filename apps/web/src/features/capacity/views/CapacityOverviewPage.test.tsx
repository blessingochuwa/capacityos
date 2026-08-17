import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CapacityOverviewPage } from './CapacityOverviewPage'
import { useTeams } from '@/hooks/useTeams'
import { usePeopleLookup } from '@/hooks/usePeople'
import { useTeamCapacity } from '../hooks/useTeamCapacity'
import { useAiSummary } from '@/features/ai/hooks/useAiSummary'
import {
  mockQueryError,
  mockQueryPending,
  mockQuerySuccess,
} from '@/test/mockQueryResult'
import {
  makePerson,
  makeTeam,
  makeTeamCapacity,
  makePersonCapacity,
} from '@/test/fixtures'

vi.mock('@/hooks/useTeams')
vi.mock('@/hooks/usePeople')
vi.mock('../hooks/useTeamCapacity')
vi.mock('@/features/ai/hooks/useAiSummary')

const mockedUseTeams = vi.mocked(useTeams)
const mockedUsePeopleLookup = vi.mocked(usePeopleLookup)
const mockedUseTeamCapacity = vi.mocked(useTeamCapacity)
const mockedUseAiSummary = vi.mocked(useAiSummary)

function renderAt(path: string) {
  mockedUseAiSummary.mockReturnValue({
    mutate: vi.fn(),
    data: undefined,
    isPending: false,
    isError: false,
    error: null,
  } as unknown as ReturnType<typeof useAiSummary>)
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CapacityOverviewPage />
    </MemoryRouter>,
  )
}

describe('CapacityOverviewPage', () => {
  it('prompts for a team when none is selected', () => {
    mockedUseTeams.mockReturnValue(
      mockQuerySuccess({
        items: [
          makeTeam({ id: 'team-1' }),
          makeTeam({ id: 'team-2', name: 'Platform' }),
        ],
        total: 2,
      }),
    )
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockedUseTeamCapacity.mockReturnValue(mockQueryPending())

    renderAt('/capacity')

    expect(
      screen.getByText('Select a team to view capacity.'),
    ).toBeInTheDocument()
  })

  it('renders a loading state while team capacity is being fetched', () => {
    mockedUseTeams.mockReturnValue(
      mockQuerySuccess({ items: [makeTeam()], total: 1 }),
    )
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockedUseTeamCapacity.mockReturnValue(mockQueryPending())

    renderAt('/capacity?team=team-1')

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders team capacity data on success, including over-allocated/available counts', () => {
    const overloaded = makePersonCapacity({
      person_id: 'p-over',
      allocated_hours: '48.00',
      remaining_capacity: '-8.00',
      over_allocation: '8.00',
      utilization: '1.2000',
    })
    const available = makePersonCapacity({
      person_id: 'p-available',
      allocated_hours: '10.00',
      remaining_capacity: '30.00',
      utilization: '0.2500',
    })

    mockedUseTeams.mockReturnValue(
      mockQuerySuccess({ items: [makeTeam()], total: 1 }),
    )
    mockedUsePeopleLookup.mockReturnValue(
      new Map([
        [
          'p-over',
          makePerson({ id: 'p-over', display_name: 'Over Allocated' }),
        ],
        [
          'p-available',
          makePerson({ id: 'p-available', display_name: 'Has Room' }),
        ],
      ]),
    )
    mockedUseTeamCapacity.mockReturnValue(
      mockQuerySuccess(
        makeTeamCapacity({
          effective_capacity: '80.00',
          allocated_hours: '58.00',
          remaining_capacity: '22.00',
          utilization: '0.7250',
          members: [overloaded, available],
        }),
      ),
    )

    renderAt('/capacity?team=team-1')

    expect(screen.getByText('People over capacity')).toBeInTheDocument()
    expect(
      screen.getByText('People with available capacity'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('Over Allocated').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Has Room').length).toBeGreaterThan(0)
  })

  it('renders an error state with a retry action when team capacity fails to load', () => {
    mockedUseTeams.mockReturnValue(
      mockQuerySuccess({ items: [makeTeam()], total: 1 }),
    )
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockedUseTeamCapacity.mockReturnValue(mockQueryError())

    renderAt('/capacity?team=team-1')

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})

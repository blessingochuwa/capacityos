import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProjectCapacityPage } from './ProjectCapacityPage'
import { usePeopleLookup } from '@/hooks/usePeople'
import { useProjectsLookup } from '@/hooks/useProjects'
import { useProjectDemand } from '../hooks/useProjectDemand'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import { makePerson, makeProject, makeProjectDemand } from '@/test/fixtures'

vi.mock('@/hooks/usePeople')
vi.mock('@/hooks/useProjects')
vi.mock('../hooks/useProjectDemand')

const mockedUsePeopleLookup = vi.mocked(usePeopleLookup)
const mockedUseProjectsLookup = vi.mocked(useProjectsLookup)
const mockedUseProjectDemand = vi.mocked(useProjectDemand)

function renderPage(projectId = 'proj-1') {
  return render(
    <MemoryRouter initialEntries={[`/capacity/projects/${projectId}`]}>
      <Routes>
        <Route
          path="/capacity/projects/:projectId"
          element={<ProjectCapacityPage />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProjectCapacityPage', () => {
  it('renders demand totals and the by-person breakdown', () => {
    mockedUseProjectsLookup.mockReturnValue(
      new Map([
        ['proj-1', makeProject({ id: 'proj-1', name: 'Mobile App Launch' })],
      ]),
    )
    mockedUsePeopleLookup.mockReturnValue(
      new Map([['p-1', makePerson({ id: 'p-1', display_name: 'Casey Kim' })]]),
    )
    mockedUseProjectDemand.mockReturnValue(
      mockQuerySuccess(
        makeProjectDemand({
          allocated_hours: '32.00',
          allocated_people: 1,
          by_person: [{ person_id: 'p-1', allocated_hours: '32.00' }],
        }),
      ),
    )

    renderPage('proj-1')

    expect(
      screen.getByRole('heading', { name: 'Mobile App Launch' }),
    ).toBeInTheDocument()
    expect(screen.getAllByText('32h').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Casey Kim').length).toBeGreaterThan(0)
  })

  it('shows an empty state when the project has no allocations in the period', () => {
    mockedUseProjectsLookup.mockReturnValue(
      new Map([['proj-1', makeProject({ id: 'proj-1' })]]),
    )
    mockedUsePeopleLookup.mockReturnValue(new Map())
    mockedUseProjectDemand.mockReturnValue(
      mockQuerySuccess(
        makeProjectDemand({
          allocated_hours: '0.00',
          allocated_people: 0,
          daily_breakdown: [],
          by_person: [],
        }),
      ),
    )

    renderPage('proj-1')

    expect(
      screen.getAllByText('No allocations found for this period.').length,
    ).toBeGreaterThan(0)
  })
})

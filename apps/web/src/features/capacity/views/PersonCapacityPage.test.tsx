import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { PersonCapacityPage } from './PersonCapacityPage'
import { usePeopleLookup } from '@/hooks/usePeople'
import { useProjectsLookup } from '@/hooks/useProjects'
import { usePersonCapacity } from '../hooks/usePersonCapacity'
import {
  usePersonAllocations,
  usePersonAvailabilityExceptions,
} from '../hooks/usePersonAllocations'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import { makePerson, makePersonCapacity } from '@/test/fixtures'

vi.mock('@/hooks/usePeople')
vi.mock('@/hooks/useProjects')
vi.mock('../hooks/usePersonCapacity')
vi.mock('../hooks/usePersonAllocations')

const mockedUsePeopleLookup = vi.mocked(usePeopleLookup)
const mockedUseProjectsLookup = vi.mocked(useProjectsLookup)
const mockedUsePersonCapacity = vi.mocked(usePersonCapacity)
const mockedUsePersonAllocations = vi.mocked(usePersonAllocations)
const mockedUsePersonAvailabilityExceptions = vi.mocked(
  usePersonAvailabilityExceptions,
)

function renderPage(personId = 'p-1') {
  return render(
    <MemoryRouter initialEntries={[`/capacity/people/${personId}`]}>
      <Routes>
        <Route
          path="/capacity/people/:personId"
          element={<PersonCapacityPage />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PersonCapacityPage', () => {
  it('shows "No effective capacity" instead of a null/percentage when utilization is null', () => {
    mockedUsePeopleLookup.mockReturnValue(
      new Map([['p-1', makePerson({ id: 'p-1', display_name: 'Riley Chen' })]]),
    )
    mockedUseProjectsLookup.mockReturnValue(new Map())
    mockedUsePersonCapacity.mockReturnValue(
      mockQuerySuccess(
        makePersonCapacity({
          person_id: 'p-1',
          effective_capacity: '0.00',
          allocated_hours: '16.00',
          remaining_capacity: '-16.00',
          over_allocation: '16.00',
          utilization: null,
          daily_breakdown: [],
        }),
      ),
    )
    mockedUsePersonAllocations.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )
    mockedUsePersonAvailabilityExceptions.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )

    renderPage('p-1')

    expect(screen.getByText('Riley Chen')).toBeInTheDocument()
    expect(screen.getByText('No effective capacity')).toBeInTheDocument()
    expect(screen.queryByText('null')).not.toBeInTheDocument()
  })

  it('makes over-allocation visible as a fact, not hidden behind the summary', () => {
    mockedUsePeopleLookup.mockReturnValue(
      new Map([['p-1', makePerson({ id: 'p-1', display_name: 'Sam Ade' })]]),
    )
    mockedUseProjectsLookup.mockReturnValue(new Map())
    mockedUsePersonCapacity.mockReturnValue(
      mockQuerySuccess(
        makePersonCapacity({
          person_id: 'p-1',
          effective_capacity: '40.00',
          allocated_hours: '44.00',
          remaining_capacity: '-4.00',
          over_allocation: '4.00',
          utilization: '1.1000',
          daily_breakdown: [],
        }),
      ),
    )
    mockedUsePersonAllocations.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )
    mockedUsePersonAvailabilityExceptions.mockReturnValue(
      mockQuerySuccess({ items: [], total: 0 }),
    )

    renderPage('p-1')

    expect(screen.getByText('Over capacity')).toBeInTheDocument()
    expect(screen.getByText('4h over')).toBeInTheDocument()
    expect(screen.getByText('110%')).toBeInTheDocument()
  })
})

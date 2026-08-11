import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { TeamCapacityTable } from './TeamCapacityTable'
import type { PersonCapacity } from '../types/capacity'
import type { Person } from '@/types/entities'

function makePerson(id: string, name: string): Person {
  return {
    id,
    first_name: name,
    last_name: '',
    display_name: name,
    email: `${name}@example.com`,
    job_title: null,
    timezone: 'UTC',
    employment_status: 'active',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

function makeCapacity(
  personId: string,
  overrides: Partial<PersonCapacity> = {},
): PersonCapacity {
  return {
    person_id: personId,
    start_date: '2026-08-17',
    end_date: '2026-08-21',
    gross_capacity: '40.00',
    unavailable_hours: '0.00',
    effective_capacity: '40.00',
    allocated_hours: '20.00',
    remaining_capacity: '20.00',
    utilization: '0.5000',
    over_allocation: '0.00',
    daily_breakdown: [],
    ...overrides,
  }
}

describe('TeamCapacityTable', () => {
  it('renders a healthy person and an over-allocated person, over-allocated first', () => {
    const healthy = makeCapacity('healthy-id')
    const overloaded = makeCapacity('overloaded-id', {
      allocated_hours: '48.00',
      remaining_capacity: '-8.00',
      utilization: '1.2000',
      over_allocation: '8.00',
    })
    const peopleLookup = new Map([
      ['healthy-id', makePerson('healthy-id', 'Healthy Person')],
      ['overloaded-id', makePerson('overloaded-id', 'Overloaded Person')],
    ])

    render(
      <MemoryRouter>
        <TeamCapacityTable
          members={[healthy, overloaded]}
          peopleLookup={peopleLookup}
        />
      </MemoryRouter>,
    )

    const rows = screen.getAllByRole('row').slice(1) // skip header row
    expect(rows[0]).toHaveTextContent('Overloaded Person')
    expect(rows[1]).toHaveTextContent('Healthy Person')
    expect(screen.getByText('Over capacity')).toBeInTheDocument()
  })

  it('shows an empty state when there are no members', () => {
    render(
      <MemoryRouter>
        <TeamCapacityTable members={[]} peopleLookup={new Map()} />
      </MemoryRouter>,
    )
    expect(
      screen.getByText('No team members match this filter.'),
    ).toBeInTheDocument()
  })
})

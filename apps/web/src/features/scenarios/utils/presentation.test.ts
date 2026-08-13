import { describe, expect, it } from 'vitest'
import {
  describeOperation,
  formatCountDelta,
  formatHoursDelta,
  formatUtilizationDelta,
} from './presentation'
import { makeScenarioOperation } from '@/test/fixtures'
import type { NameLookup } from './presentation'

const names: NameLookup = {
  personLabel: (id) => (id === 'person-1' ? 'Sarah' : 'Alex'),
  projectLabel: () => 'Website Redesign',
}

describe('describeOperation', () => {
  it('describes add_allocation in plain language', () => {
    const operation = makeScenarioOperation()
    expect(describeOperation(operation, names)).toBe(
      'Add 20h for Sarah on Website Redesign (Sep 1 – Sep 5)',
    )
  })

  it('describes move_allocation with a destination person', () => {
    const operation = makeScenarioOperation({
      operation_type: 'move_allocation',
      payload: {
        operation_type: 'move_allocation',
        allocation_id: 'alloc-1',
        to_person_id: 'person-2',
        hours: '10',
      },
    })
    expect(describeOperation(operation, names)).toBe('Move 10h to Alex')
  })

  it('describes shift_project with direction', () => {
    const operation = makeScenarioOperation({
      operation_type: 'shift_project',
      payload: {
        operation_type: 'shift_project',
        project_id: 'project-1',
        day_offset: -7,
      },
    })
    expect(describeOperation(operation, names)).toBe(
      'Website Redesign starts 7 days earlier',
    )
  })

  it('describes availability_override as fully unavailable when hours is null', () => {
    const operation = makeScenarioOperation({
      operation_type: 'availability_override',
      payload: {
        operation_type: 'availability_override',
        person_id: 'person-1',
        start_date: '2026-09-01',
        end_date: '2026-09-05',
        hours: null,
      },
    })
    expect(describeOperation(operation, names)).toBe(
      'Sarah is unavailable Sep 1 – Sep 5',
    )
  })

  it('describes add_hypothetical_resource with its label', () => {
    const operation = makeScenarioOperation({
      operation_type: 'add_hypothetical_resource',
      payload: {
        operation_type: 'add_hypothetical_resource',
        label: 'Senior Designer',
        hours_per_week: '40',
        start_date: '2026-09-01',
        end_date: '2026-09-05',
      },
    })
    expect(describeOperation(operation, names)).toBe(
      'Add hypothetical "Senior Designer" — 40h/week (Sep 1 – Sep 5)',
    )
  })
})

describe('formatUtilizationDelta', () => {
  it('renders a positive delta with a leading plus sign', () => {
    expect(formatUtilizationDelta('0.13')).toBe('+13pp')
  })

  it('renders a negative delta', () => {
    expect(formatUtilizationDelta('-0.05')).toBe('-5pp')
  })

  it('renders null as an em dash', () => {
    expect(formatUtilizationDelta(null)).toBe('—')
  })
})

describe('formatHoursDelta', () => {
  it('renders a positive delta with a leading plus sign', () => {
    expect(formatHoursDelta('6')).toBe('+6h')
  })

  it('renders a negative delta', () => {
    expect(formatHoursDelta('-26')).toBe('-26h')
  })

  it('renders zero without a sign', () => {
    expect(formatHoursDelta('0')).toBe('0h')
  })
})

describe('formatCountDelta', () => {
  it('renders a positive delta with a leading plus sign', () => {
    expect(formatCountDelta(2)).toBe('+2')
  })

  it('renders zero without a sign', () => {
    expect(formatCountDelta(0)).toBe('0')
  })
})

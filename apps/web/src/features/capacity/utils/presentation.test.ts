import { describe, expect, it } from 'vitest'
import {
  formatAvailabilityType,
  formatHours,
  formatOverAllocation,
  formatUtilization,
  getCapacityStatus,
} from './presentation'

describe('getCapacityStatus', () => {
  it('is "over" whenever over_allocation is positive, regardless of utilization', () => {
    expect(getCapacityStatus('1.2500', '8.00')).toBe('over')
    // Even a nonsensical/edge utilization value must not override a real over-allocation fact.
    expect(getCapacityStatus('0.1000', '0.01')).toBe('over')
  })

  it('is "no-data" when utilization is null, never "under"', () => {
    expect(getCapacityStatus(null, '0.00')).toBe('no-data')
  })

  it('is "at" at or above the 90% threshold with no over-allocation', () => {
    expect(getCapacityStatus('0.9000', '0.00')).toBe('at')
    expect(getCapacityStatus('1.0000', '0.00')).toBe('at')
  })

  it('is "under" below the threshold with no over-allocation', () => {
    expect(getCapacityStatus('0.5000', '0.00')).toBe('under')
    expect(getCapacityStatus('0.8999', '0.00')).toBe('under')
  })
})

describe('formatHours', () => {
  it('drops a trailing .0', () => {
    expect(formatHours('8.00')).toBe('8h')
  })

  it('rounds to at most one decimal place', () => {
    expect(formatHours('6.666666666666666666666666667')).toBe('6.7h')
  })
})

describe('formatUtilization', () => {
  it('never renders the literal word "null" — shows a human explanation instead', () => {
    expect(formatUtilization(null)).toBe('No effective capacity')
    expect(formatUtilization(null)).not.toMatch(/null/i)
  })

  it('renders a whole-number percentage, not false precision', () => {
    expect(formatUtilization('0.82376492')).toBe('82%')
  })

  it('renders over 100% for over-allocation', () => {
    expect(formatUtilization('1.2500')).toBe('125%')
  })
})

describe('formatOverAllocation', () => {
  it('returns null (nothing to show) when there is no over-allocation', () => {
    expect(formatOverAllocation('0.00')).toBeNull()
  })

  it('returns a labeled hours string when over-allocated', () => {
    expect(formatOverAllocation('8.00')).toBe('8h over')
  })
})

describe('formatAvailabilityType', () => {
  it('turns the controlled-vocabulary value into a readable label', () => {
    expect(formatAvailabilityType('annual_leave')).toBe('Annual leave')
    expect(formatAvailabilityType('public_holiday')).toBe('Public holiday')
  })
})

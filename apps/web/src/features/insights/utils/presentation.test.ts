import { describe, expect, it } from 'vitest'
import { bottomUtilization, sortSignals, topUtilization } from './presentation'
import { makeSignal } from '@/test/fixtures'

describe('sortSignals', () => {
  it('sorts critical severity before info, regardless of input order', () => {
    const info = makeSignal({
      type: 'concentration_risk',
      severity: 'info',
      entity_label: 'B',
    })
    const critical = makeSignal({
      type: 'over_allocation',
      severity: 'critical',
      entity_label: 'A',
    })

    const sorted = sortSignals([info, critical])
    expect(sorted[0]).toBe(critical)
    expect(sorted[1]).toBe(info)
  })

  it('within the same severity, ranks a new scenario risk before an existing one', () => {
    const existing = makeSignal({
      type: 'scenario_existing_risk',
      severity: 'critical',
      is_new: false,
      entity_label: 'A',
    })
    const brandNew = makeSignal({
      type: 'scenario_new_risk',
      severity: 'critical',
      is_new: true,
      entity_label: 'B',
    })

    const sorted = sortSignals([existing, brandNew])
    expect(sorted[0]).toBe(brandNew)
    expect(sorted[1]).toBe(existing)
  })

  it('breaks ties deterministically by entity label', () => {
    const zed = makeSignal({ entity_label: 'Zed', entity_id: 'p-2' })
    const anna = makeSignal({ entity_label: 'Anna', entity_id: 'p-1' })

    const sorted = sortSignals([zed, anna])
    expect(sorted[0]).toBe(anna)
    expect(sorted[1]).toBe(zed)
  })
})

describe('topUtilization / bottomUtilization', () => {
  const points = [
    { person_id: 'a', label: 'A', utilization: '1.2000' },
    { person_id: 'b', label: 'B', utilization: '0.8000' },
    { person_id: 'c', label: 'C', utilization: '0.4200' },
  ]

  it('topUtilization slices from the front without re-sorting', () => {
    expect(topUtilization(points, 2)).toEqual([points[0], points[1]])
  })

  it('bottomUtilization slices from the back, lowest first', () => {
    expect(bottomUtilization(points, 2)).toEqual([points[2], points[1]])
  })
})

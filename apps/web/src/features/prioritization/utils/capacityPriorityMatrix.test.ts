import { describe, expect, it } from 'vitest'
import { buildCapacityPriorityMatrix } from './capacityPriorityMatrix'
import { makeAllocation, makePortfolioRankingEntry } from '@/test/fixtures'

describe('buildCapacityPriorityMatrix', () => {
  describe('data transformation', () => {
    it('turns a valid project into one matrix point with capacity and priority mapped correctly', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Website Redesign', score: '400' }),
      ]
      const allocations = [
        makeAllocation({ project_id: 'p1', allocation_hours: '30' }),
        makeAllocation({ project_id: 'p1', allocation_hours: '10' }),
      ]

      const model = buildCapacityPriorityMatrix(items, allocations)

      expect(model.points).toEqual([
        {
          project_id: 'p1',
          project_name: 'Website Redesign',
          capacity_hours: 40,
          priority_score: 400,
          quadrant: 'low_priority_low_capacity',
        },
      ])
      expect(model.excluded).toEqual([])
    })

    it('preserves the project name verbatim', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Mobile App Revamp' })]
      const allocations = [makeAllocation({ project_id: 'p1', allocation_hours: '20' })]

      const model = buildCapacityPriorityMatrix(items, allocations)

      expect(model.points[0].project_name).toBe('Mobile App Revamp')
    })

    it('excludes a project with no capacity data (zero recorded allocations) without fabricating zero', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', score: '400' })]

      const model = buildCapacityPriorityMatrix(items, [])

      expect(model.points).toEqual([])
      expect(model.excluded).toEqual([
        { project_id: 'p1', project_name: 'Website Redesign', reason: 'no_capacity_data' },
      ])
    })

    it('excludes a project with no priority score without fabricating zero', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', score: null, missing_criteria: ['effort'] })]
      const allocations = [makeAllocation({ project_id: 'p1', allocation_hours: '20' })]

      const model = buildCapacityPriorityMatrix(items, allocations)

      expect(model.points).toEqual([])
      expect(model.excluded).toEqual([
        { project_id: 'p1', project_name: 'Website Redesign', reason: 'no_priority_score' },
      ])
    })

    it('excludes a project missing both priority score and capacity data', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', score: null })]

      const model = buildCapacityPriorityMatrix(items, [])

      expect(model.excluded).toEqual([
        {
          project_id: 'p1',
          project_name: 'Website Redesign',
          reason: 'no_priority_score_and_no_capacity_data',
        },
      ])
    })

    it('never uses zero as a substitute for a missing capacity or priority value', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'no-capacity', score: '100' }),
        makePortfolioRankingEntry({ project_id: 'no-priority', score: null }),
      ]
      const allocations = [makeAllocation({ project_id: 'no-priority', allocation_hours: '10' })]

      const model = buildCapacityPriorityMatrix(items, allocations)

      // Neither excluded project appears as a plotted point at 0 — they are
      // absent from `points` entirely, not present with a fabricated value.
      expect(model.points).toEqual([])
      expect(model.points.some((p) => p.project_id === 'no-capacity')).toBe(false)
      expect(model.points.some((p) => p.project_id === 'no-priority')).toBe(false)
    })

    it('sums multiple allocations across different people for the same project', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', score: '50' })]
      const allocations = [
        makeAllocation({ project_id: 'p1', person_id: 'person-a', allocation_hours: '15.5' }),
        makeAllocation({ project_id: 'p1', person_id: 'person-b', allocation_hours: '24.5' }),
      ]

      const model = buildCapacityPriorityMatrix(items, allocations)

      expect(model.points[0].capacity_hours).toBe(40)
    })

    it('ignores allocations belonging to projects not in the portfolio ranking', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', score: '50' })]
      const allocations = [
        makeAllocation({ project_id: 'p1', allocation_hours: '10' }),
        makeAllocation({ project_id: 'other-project', allocation_hours: '999' }),
      ]

      const model = buildCapacityPriorityMatrix(items, allocations)

      expect(model.points[0].capacity_hours).toBe(10)
    })
  })

  describe('median / quadrant logic', () => {
    it('calculates median capacity and median priority correctly (odd count)', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'p1', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'p2', score: '20' }),
        makePortfolioRankingEntry({ project_id: 'p3', score: '30' }),
      ]
      const allocations = [
        makeAllocation({ project_id: 'p1', allocation_hours: '5' }),
        makeAllocation({ project_id: 'p2', allocation_hours: '15' }),
        makeAllocation({ project_id: 'p3', allocation_hours: '25' }),
      ]

      const model = buildCapacityPriorityMatrix(items, allocations)

      expect(model.medianCapacity).toBe(15)
      expect(model.medianPriority).toBe(20)
    })

    it('calculates median capacity and median priority correctly (even count, averages the middle two)', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'p1', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'p2', score: '20' }),
        makePortfolioRankingEntry({ project_id: 'p3', score: '30' }),
        makePortfolioRankingEntry({ project_id: 'p4', score: '40' }),
      ]
      const allocations = [
        makeAllocation({ project_id: 'p1', allocation_hours: '4' }),
        makeAllocation({ project_id: 'p2', allocation_hours: '8' }),
        makeAllocation({ project_id: 'p3', allocation_hours: '12' }),
        makeAllocation({ project_id: 'p4', allocation_hours: '16' }),
      ]

      const model = buildCapacityPriorityMatrix(items, allocations)

      expect(model.medianCapacity).toBe(10) // (8 + 12) / 2
      expect(model.medianPriority).toBe(25) // (20 + 30) / 2
    })

    it('classifies a project above both medians as High Priority / High Capacity', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'low', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'high', score: '90' }),
      ]
      const allocations = [
        makeAllocation({ project_id: 'low', allocation_hours: '5' }),
        makeAllocation({ project_id: 'high', allocation_hours: '95' }),
      ]

      const model = buildCapacityPriorityMatrix(items, allocations)

      const high = model.points.find((p) => p.project_id === 'high')
      expect(high?.quadrant).toBe('high_priority_high_capacity')
    })

    it('classifies a project above priority median but below capacity median as High Priority / Low Capacity', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'a', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'b', score: '90' }),
      ]
      const allocations = [
        makeAllocation({ project_id: 'a', allocation_hours: '95' }),
        makeAllocation({ project_id: 'b', allocation_hours: '5' }),
      ]

      const model = buildCapacityPriorityMatrix(items, allocations)

      const b = model.points.find((p) => p.project_id === 'b')
      expect(b?.quadrant).toBe('high_priority_low_capacity')
    })

    it('classifies a project below priority median but above capacity median as Low Priority / High Capacity', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'a', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'b', score: '90' }),
      ]
      const allocations = [
        makeAllocation({ project_id: 'a', allocation_hours: '95' }),
        makeAllocation({ project_id: 'b', allocation_hours: '5' }),
      ]

      const model = buildCapacityPriorityMatrix(items, allocations)

      const a = model.points.find((p) => p.project_id === 'a')
      expect(a?.quadrant).toBe('low_priority_high_capacity')
    })

    it('classifies a project below both medians as Low Priority / Low Capacity', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'low', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'high', score: '90' }),
      ]
      const allocations = [
        makeAllocation({ project_id: 'low', allocation_hours: '5' }),
        makeAllocation({ project_id: 'high', allocation_hours: '95' }),
      ]

      const model = buildCapacityPriorityMatrix(items, allocations)

      const low = model.points.find((p) => p.project_id === 'low')
      expect(low?.quadrant).toBe('low_priority_low_capacity')
    })

    it('deterministically classifies a value exactly equal to the median as the low side of that axis', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'p1', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'p2', score: '20' }),
        makePortfolioRankingEntry({ project_id: 'p3', score: '30' }),
      ]
      const allocations = [
        makeAllocation({ project_id: 'p1', allocation_hours: '10' }),
        makeAllocation({ project_id: 'p2', allocation_hours: '20' }),
        makeAllocation({ project_id: 'p3', allocation_hours: '30' }),
      ]

      // Median capacity = 20, median priority = 20 — p2 sits exactly on
      // both medians and must land on the "low" side of both axes.
      const model = buildCapacityPriorityMatrix(items, allocations)

      const median = model.points.find((p) => p.project_id === 'p2')
      expect(median?.quadrant).toBe('low_priority_low_capacity')
    })

    it('is deterministic for a single plotted point (equal to its own median on both axes)', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'solo', score: '42' })]
      const allocations = [makeAllocation({ project_id: 'solo', allocation_hours: '17' })]

      const model = buildCapacityPriorityMatrix(items, allocations)

      expect(model.medianCapacity).toBe(17)
      expect(model.medianPriority).toBe(42)
      expect(model.points[0].quadrant).toBe('low_priority_low_capacity')
    })

    it('computes medians only across plotted points, never excluded projects', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'plotted', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'excluded', score: null }),
      ]
      const allocations = [
        makeAllocation({ project_id: 'plotted', allocation_hours: '5' }),
        makeAllocation({ project_id: 'excluded', allocation_hours: '999' }),
      ]

      const model = buildCapacityPriorityMatrix(items, allocations)

      expect(model.medianCapacity).toBe(5)
      expect(model.medianPriority).toBe(10)
    })
  })

  it('returns null medians and no points when nothing is plottable', () => {
    const items = [makePortfolioRankingEntry({ project_id: 'p1', score: null })]

    const model = buildCapacityPriorityMatrix(items, [])

    expect(model.points).toEqual([])
    expect(model.medianCapacity).toBeNull()
    expect(model.medianPriority).toBeNull()
  })

  it('returns an empty model for an empty portfolio', () => {
    const model = buildCapacityPriorityMatrix([], [])
    expect(model).toEqual({ points: [], excluded: [], medianCapacity: null, medianPriority: null })
  })
})

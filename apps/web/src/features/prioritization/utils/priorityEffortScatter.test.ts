import { describe, expect, it } from 'vitest'
import { buildPriorityEffortScatter } from './priorityEffortScatter'
import { makePortfolioRankingEntry } from '@/test/fixtures'

describe('buildPriorityEffortScatter', () => {
  it('plots a RICE project using its effort criterion and computed score', () => {
    const item = makePortfolioRankingEntry({
      project_id: 'p1',
      project_name: 'Website Redesign',
      score: '400.00',
      breakdown: { reach: '1000', impact: '2', confidence: '0.8', effort: '4' },
    })

    expect(buildPriorityEffortScatter('rice', [item])).toEqual([
      { project_id: 'p1', project_name: 'Website Redesign', effort: 4, priority: 400 },
    ])
  })

  it('plots a WSJF project using job_size as its effort axis', () => {
    const item = makePortfolioRankingEntry({
      project_id: 'p1',
      project_name: 'Platform Migration',
      score: '4.5',
      breakdown: {
        business_value: '8',
        time_criticality: '5',
        risk_reduction_opportunity_enablement: '3',
        job_size: '2',
      },
    })

    expect(buildPriorityEffortScatter('wsjf', [item])).toEqual([
      { project_id: 'p1', project_name: 'Platform Migration', effort: 2, priority: 4.5 },
    ])
  })

  it('returns no points for a framework with no defined effort criterion', () => {
    const item = makePortfolioRankingEntry({
      score: '5.5',
      breakdown: { impact: '8', confidence: '7', ease: '2' },
    })

    expect(buildPriorityEffortScatter('ice', [item])).toEqual([])
    expect(buildPriorityEffortScatter('weighted', [item])).toEqual([])
    expect(buildPriorityEffortScatter('moscow', [item])).toEqual([])
  })

  it('excludes a project with no score (incomplete RICE inputs)', () => {
    const item = makePortfolioRankingEntry({
      score: null,
      missing_criteria: ['effort'],
      breakdown: { reach: '1000', impact: '2', confidence: '0.8' },
    })

    expect(buildPriorityEffortScatter('rice', [item])).toEqual([])
  })

  it('includes multiple fully-scored RICE projects', () => {
    const items = [
      makePortfolioRankingEntry({
        project_id: 'p1',
        score: '400.00',
        breakdown: { reach: '1000', impact: '2', confidence: '0.8', effort: '4' },
      }),
      makePortfolioRankingEntry({
        project_id: 'p2',
        score: '100.00',
        breakdown: { reach: '500', impact: '1', confidence: '0.8', effort: '4' },
      }),
    ]

    expect(buildPriorityEffortScatter('rice', items).map((p) => p.project_id)).toEqual([
      'p1',
      'p2',
    ])
  })
})

import { describe, expect, it } from 'vitest'
import { buildWsjfBreakdown } from './wsjfBreakdown'
import { makePortfolioRankingEntry } from '@/test/fixtures'

describe('buildWsjfBreakdown', () => {
  it('copies each of the four criterion values verbatim from a fully-scored project', () => {
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

    const rows = buildWsjfBreakdown([item])

    expect(rows).toEqual([
      {
        project_id: 'p1',
        project_name: 'Platform Migration',
        business_value: 8,
        time_criticality: 5,
        risk_reduction_opportunity_enablement: 3,
        job_size: 2,
      },
    ])
  })

  it('excludes a project with no score (incomplete WSJF inputs)', () => {
    const item = makePortfolioRankingEntry({
      score: null,
      missing_criteria: ['job_size'],
      breakdown: { business_value: '8', time_criticality: '5' },
    })

    expect(buildWsjfBreakdown([item])).toEqual([])
  })

  it('excludes a project scored under a different framework with no WSJF breakdown keys', () => {
    const item = makePortfolioRankingEntry({
      score: '400.00',
      breakdown: { reach: '1000', impact: '2', confidence: '0.8', effort: '4' },
    })

    expect(buildWsjfBreakdown([item])).toEqual([])
  })

  it('preserves portfolio order and includes multiple fully-scored projects', () => {
    const items = [
      makePortfolioRankingEntry({
        project_id: 'p1',
        score: '4.5',
        breakdown: {
          business_value: '8',
          time_criticality: '5',
          risk_reduction_opportunity_enablement: '3',
          job_size: '2',
        },
      }),
      makePortfolioRankingEntry({
        project_id: 'p2',
        score: '2.0',
        breakdown: {
          business_value: '4',
          time_criticality: '2',
          risk_reduction_opportunity_enablement: '2',
          job_size: '4',
        },
      }),
    ]

    expect(buildWsjfBreakdown(items).map((r) => r.project_id)).toEqual(['p1', 'p2'])
  })
})

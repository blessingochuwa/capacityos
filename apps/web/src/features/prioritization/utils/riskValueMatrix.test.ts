import { describe, expect, it } from 'vitest'
import { buildRiskValueMatrix, countOpenHighExposureRisks } from './riskValueMatrix'
import { makePortfolioRankingEntry, makeProjectRisk } from '@/test/fixtures'

describe('countOpenHighExposureRisks', () => {
  it('counts an open risk with high exposure', () => {
    const risks = [makeProjectRisk({ status: 'open', exposure: 'high' })]
    expect(countOpenHighExposureRisks(risks)).toBe(1)
  })

  it('does not count a closed risk even with high exposure', () => {
    const risks = [makeProjectRisk({ status: 'closed', exposure: 'high' })]
    expect(countOpenHighExposureRisks(risks)).toBe(0)
  })

  it('counts mitigating and monitoring risks as open', () => {
    const risks = [
      makeProjectRisk({ id: 'r1', status: 'mitigating', exposure: 'high' }),
      makeProjectRisk({ id: 'r2', status: 'monitoring', exposure: 'high' }),
    ]
    expect(countOpenHighExposureRisks(risks)).toBe(2)
  })

  it('does not count a low or medium exposure risk', () => {
    const risks = [
      makeProjectRisk({ id: 'r1', status: 'open', exposure: 'low' }),
      makeProjectRisk({ id: 'r2', status: 'open', exposure: 'medium' }),
    ]
    expect(countOpenHighExposureRisks(risks)).toBe(0)
  })

  it('returns 0 for an empty risk list', () => {
    expect(countOpenHighExposureRisks([])).toBe(0)
  })

  it('counts only the qualifying subset among a mixed list', () => {
    const risks = [
      makeProjectRisk({ id: 'r1', status: 'open', exposure: 'high' }),
      makeProjectRisk({ id: 'r2', status: 'closed', exposure: 'high' }),
      makeProjectRisk({ id: 'r3', status: 'open', exposure: 'low' }),
      makeProjectRisk({ id: 'r4', status: 'monitoring', exposure: 'high' }),
    ]
    expect(countOpenHighExposureRisks(risks)).toBe(2)
  })
})

describe('buildRiskValueMatrix', () => {
  describe('data transformation', () => {
    it('turns a valid project into one matrix point with risk and value mapped correctly', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Website Redesign', score: '400' }),
      ]
      const riskCounts = new Map([['p1', 3]])

      const model = buildRiskValueMatrix(items, riskCounts)

      expect(model.points).toEqual([
        {
          project_id: 'p1',
          project_name: 'Website Redesign',
          risk_count: 3,
          value_score: 400,
          quadrant: 'low_value_low_risk',
        },
      ])
      expect(model.excluded).toEqual([])
    })

    it('preserves the project name verbatim', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Mobile App Revamp' })]
      const riskCounts = new Map([['p1', 0]])

      const model = buildRiskValueMatrix(items, riskCounts)

      expect(model.points[0].project_name).toBe('Mobile App Revamp')
    })

    it('includes a project with a real zero risk count as a plotted point, not excluded', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', score: '400' })]
      const riskCounts = new Map([['p1', 0]])

      const model = buildRiskValueMatrix(items, riskCounts)

      expect(model.points).toHaveLength(1)
      expect(model.points[0].risk_count).toBe(0)
      expect(model.excluded).toEqual([])
    })

    it('excludes a project whose risk data is unavailable (fetch never succeeded) without fabricating zero', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', score: '400' })]

      const model = buildRiskValueMatrix(items, new Map())

      expect(model.points).toEqual([])
      expect(model.excluded).toEqual([
        { project_id: 'p1', project_name: 'Website Redesign', reason: 'risk_data_unavailable' },
      ])
    })

    it('excludes a project with no priority score without fabricating zero', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', score: null, missing_criteria: ['effort'] })]
      const riskCounts = new Map([['p1', 2]])

      const model = buildRiskValueMatrix(items, riskCounts)

      expect(model.points).toEqual([])
      expect(model.excluded).toEqual([
        { project_id: 'p1', project_name: 'Website Redesign', reason: 'no_priority_score' },
      ])
    })

    it('excludes a project missing both priority score and risk data', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', score: null })]

      const model = buildRiskValueMatrix(items, new Map())

      expect(model.excluded).toEqual([
        {
          project_id: 'p1',
          project_name: 'Website Redesign',
          reason: 'no_priority_score_and_risk_data_unavailable',
        },
      ])
    })

    it('never uses zero as a substitute for a missing value or unavailable risk data', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'no-risk-data', score: '100' }),
        makePortfolioRankingEntry({ project_id: 'no-value', score: null }),
      ]
      const riskCounts = new Map([['no-value', 2]])

      const model = buildRiskValueMatrix(items, riskCounts)

      expect(model.points).toEqual([])
      expect(model.points.some((p) => p.project_id === 'no-risk-data')).toBe(false)
      expect(model.points.some((p) => p.project_id === 'no-value')).toBe(false)
    })

    it('ignores risk-count entries for projects not in the portfolio ranking', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'p1', score: '50' })]
      const riskCounts = new Map([
        ['p1', 1],
        ['unrelated-project', 999],
      ])

      const model = buildRiskValueMatrix(items, riskCounts)

      expect(model.points).toHaveLength(1)
      expect(model.points[0].risk_count).toBe(1)
    })
  })

  describe('median / quadrant logic', () => {
    it('calculates median risk and median value correctly (odd count)', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'p1', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'p2', score: '20' }),
        makePortfolioRankingEntry({ project_id: 'p3', score: '30' }),
      ]
      const riskCounts = new Map([
        ['p1', 1],
        ['p2', 3],
        ['p3', 5],
      ])

      const model = buildRiskValueMatrix(items, riskCounts)

      expect(model.medianRisk).toBe(3)
      expect(model.medianValue).toBe(20)
    })

    it('calculates median risk and median value correctly (even count, averages the middle two)', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'p1', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'p2', score: '20' }),
        makePortfolioRankingEntry({ project_id: 'p3', score: '30' }),
        makePortfolioRankingEntry({ project_id: 'p4', score: '40' }),
      ]
      const riskCounts = new Map([
        ['p1', 0],
        ['p2', 2],
        ['p3', 4],
        ['p4', 6],
      ])

      const model = buildRiskValueMatrix(items, riskCounts)

      expect(model.medianRisk).toBe(3) // (2 + 4) / 2
      expect(model.medianValue).toBe(25) // (20 + 30) / 2
    })

    it('classifies a project above both medians as High Value / High Risk', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'low', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'high', score: '90' }),
      ]
      const riskCounts = new Map([
        ['low', 1],
        ['high', 9],
      ])

      const model = buildRiskValueMatrix(items, riskCounts)

      const high = model.points.find((p) => p.project_id === 'high')
      expect(high?.quadrant).toBe('high_value_high_risk')
    })

    it('classifies a project above value median but below risk median as High Value / Low Risk', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'a', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'b', score: '90' }),
      ]
      const riskCounts = new Map([
        ['a', 9],
        ['b', 1],
      ])

      const model = buildRiskValueMatrix(items, riskCounts)

      const b = model.points.find((p) => p.project_id === 'b')
      expect(b?.quadrant).toBe('high_value_low_risk')
    })

    it('classifies a project below value median but above risk median as Low Value / High Risk', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'a', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'b', score: '90' }),
      ]
      const riskCounts = new Map([
        ['a', 9],
        ['b', 1],
      ])

      const model = buildRiskValueMatrix(items, riskCounts)

      const a = model.points.find((p) => p.project_id === 'a')
      expect(a?.quadrant).toBe('low_value_high_risk')
    })

    it('classifies a project below both medians as Low Value / Low Risk', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'low', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'high', score: '90' }),
      ]
      const riskCounts = new Map([
        ['low', 1],
        ['high', 9],
      ])

      const model = buildRiskValueMatrix(items, riskCounts)

      const low = model.points.find((p) => p.project_id === 'low')
      expect(low?.quadrant).toBe('low_value_low_risk')
    })

    it('deterministically classifies a value exactly equal to the median as the low side of that axis', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'p1', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'p2', score: '20' }),
        makePortfolioRankingEntry({ project_id: 'p3', score: '30' }),
      ]
      const riskCounts = new Map([
        ['p1', 1],
        ['p2', 2],
        ['p3', 3],
      ])

      // Median risk = 2, median value = 20 — p2 sits exactly on both
      // medians and must land on the "low" side of both axes.
      const model = buildRiskValueMatrix(items, riskCounts)

      const middle = model.points.find((p) => p.project_id === 'p2')
      expect(middle?.quadrant).toBe('low_value_low_risk')
    })

    it('is deterministic for a single plotted point (equal to its own median on both axes)', () => {
      const items = [makePortfolioRankingEntry({ project_id: 'solo', score: '42' })]
      const riskCounts = new Map([['solo', 4]])

      const model = buildRiskValueMatrix(items, riskCounts)

      expect(model.medianRisk).toBe(4)
      expect(model.medianValue).toBe(42)
      expect(model.points[0].quadrant).toBe('low_value_low_risk')
    })

    it('computes medians only across plotted points, never excluded projects', () => {
      const items = [
        makePortfolioRankingEntry({ project_id: 'plotted', score: '10' }),
        makePortfolioRankingEntry({ project_id: 'excluded', score: null }),
      ]
      const riskCounts = new Map([
        ['plotted', 1],
        ['excluded', 999],
      ])

      const model = buildRiskValueMatrix(items, riskCounts)

      expect(model.medianRisk).toBe(1)
      expect(model.medianValue).toBe(10)
    })
  })

  it('returns null medians and no points when nothing is plottable', () => {
    const items = [makePortfolioRankingEntry({ project_id: 'p1', score: null })]

    const model = buildRiskValueMatrix(items, new Map())

    expect(model.points).toEqual([])
    expect(model.medianRisk).toBeNull()
    expect(model.medianValue).toBeNull()
  })

  it('returns an empty model for an empty portfolio', () => {
    const model = buildRiskValueMatrix([], new Map())
    expect(model).toEqual({ points: [], excluded: [], medianRisk: null, medianValue: null })
  })
})

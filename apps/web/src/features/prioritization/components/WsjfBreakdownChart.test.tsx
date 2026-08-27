import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WsjfBreakdownChart } from './WsjfBreakdownChart'
import { makePortfolioRankingEntry } from '@/test/fixtures'

describe('WsjfBreakdownChart', () => {
  it('renders an empty state when no project has a complete WSJF score', () => {
    const item = makePortfolioRankingEntry({
      score: null,
      breakdown: { business_value: '8' },
    })
    render(<WsjfBreakdownChart items={[item]} />)
    expect(screen.getByText('No projects have a complete WSJF score yet.')).toBeInTheDocument()
  })

  it('renders the breakdown table with each criterion value for a fully-scored project', () => {
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
    render(<WsjfBreakdownChart items={[item]} />)

    expect(screen.getByText('Platform Migration')).toBeInTheDocument()
    const row = screen.getByText('Platform Migration').closest('tr')
    expect(row).not.toBeNull()
    expect(row?.textContent).toContain('8')
    expect(row?.textContent).toContain('5')
    expect(row?.textContent).toContain('3')
    expect(row?.textContent).toContain('2')
  })

  it('excludes a project scored under a non-WSJF framework from the table', () => {
    const item = makePortfolioRankingEntry({
      project_name: 'Website Redesign',
      score: '400.00',
      breakdown: { reach: '1000', impact: '2', confidence: '0.8', effort: '4' },
    })
    render(<WsjfBreakdownChart items={[item]} />)
    expect(screen.getByText('No projects have a complete WSJF score yet.')).toBeInTheDocument()
  })
})

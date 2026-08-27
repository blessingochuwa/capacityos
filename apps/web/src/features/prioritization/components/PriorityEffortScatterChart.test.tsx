import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PriorityEffortScatterChart } from './PriorityEffortScatterChart'
import { makePortfolioRankingEntry } from '@/test/fixtures'

describe('PriorityEffortScatterChart', () => {
  it('renders an empty state when the framework has no defined effort criterion', () => {
    const item = makePortfolioRankingEntry({
      score: '5.5',
      breakdown: { impact: '8', confidence: '7', ease: '2' },
    })
    render(<PriorityEffortScatterChart frameworkType="ice" items={[item]} />)
    expect(screen.getByText('No projects have a complete score to plot yet.')).toBeInTheDocument()
  })

  it('renders the accessible table with priority and effort for a fully-scored RICE project', () => {
    const item = makePortfolioRankingEntry({
      project_id: 'p1',
      project_name: 'Website Redesign',
      score: '400.00',
      breakdown: { reach: '1000', impact: '2', confidence: '0.8', effort: '4' },
    })
    render(<PriorityEffortScatterChart frameworkType="rice" items={[item]} />)

    expect(screen.getByText('Website Redesign')).toBeInTheDocument()
    const row = screen.getByText('Website Redesign').closest('tr')
    expect(row).not.toBeNull()
    expect(row?.textContent).toContain('400')
    expect(row?.textContent).toContain('4')
  })

  it('renders a WSJF project using job_size as the effort value', () => {
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
    render(<PriorityEffortScatterChart frameworkType="wsjf" items={[item]} />)

    const row = screen.getByText('Platform Migration').closest('tr')
    expect(row).not.toBeNull()
    expect(row?.textContent).toContain('4.5')
    expect(row?.textContent).toContain('2')
  })
})

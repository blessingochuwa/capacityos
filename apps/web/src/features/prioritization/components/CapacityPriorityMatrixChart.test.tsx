import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { CapacityPriorityMatrixChart } from './CapacityPriorityMatrixChart'
import { makeAllocation, makePortfolioRankingEntry } from '@/test/fixtures'

describe('CapacityPriorityMatrixChart', () => {
  it('shows an explanatory empty state when no project has both a priority score and capacity value', () => {
    render(<CapacityPriorityMatrixChart items={[]} allocations={[]} />)

    expect(
      screen.getByText('No projects have both a priority score and capacity data to plot yet.'),
    ).toBeInTheDocument()
  })

  it('shows the empty state when projects exist but none are plottable', () => {
    const items = [makePortfolioRankingEntry({ project_id: 'p1', score: null })]
    render(<CapacityPriorityMatrixChart items={items} allocations={[]} />)

    expect(
      screen.getByText('No projects have both a priority score and capacity data to plot yet.'),
    ).toBeInTheDocument()
  })

  it('renders a valid project as a row with capacity, priority, and quadrant', () => {
    const items = [
      makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Website Redesign', score: '90' }),
    ]
    const allocations = [makeAllocation({ project_id: 'p1', allocation_hours: '40' })]

    render(<CapacityPriorityMatrixChart items={items} allocations={allocations} />)

    const table = screen.getByRole('table', { name: 'Capacity vs. priority matrix' })
    const row = within(table).getByText('Website Redesign').closest('tr')
    expect(row?.textContent).toContain('40')
    expect(row?.textContent).toContain('90')
    expect(row?.textContent).toContain('Low Priority / Low Capacity')
  })

  it('renders all four quadrant labels and descriptions', () => {
    const items = [
      makePortfolioRankingEntry({ project_id: 'low', project_name: 'Low/Low', score: '10' }),
      makePortfolioRankingEntry({ project_id: 'high', project_name: 'High/High', score: '90' }),
    ]
    const allocations = [
      makeAllocation({ project_id: 'low', allocation_hours: '5' }),
      makeAllocation({ project_id: 'high', allocation_hours: '95' }),
    ]

    render(<CapacityPriorityMatrixChart items={items} allocations={allocations} />)

    // Each label appears at least once in the quadrant legend; some also
    // appear a second time in the table (one per matching row), so this
    // asserts presence rather than an exact count.
    expect(screen.getAllByText('High Priority / High Capacity').length).toBeGreaterThan(0)
    expect(screen.getAllByText('High Priority / Low Capacity').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Low Priority / High Capacity').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Low Priority / Low Capacity').length).toBeGreaterThan(0)
  })

  it('describes the median reference lines as text, not only as chart position', () => {
    const items = [
      makePortfolioRankingEntry({ project_id: 'p1', score: '10' }),
      makePortfolioRankingEntry({ project_id: 'p2', score: '30' }),
    ]
    const allocations = [
      makeAllocation({ project_id: 'p1', allocation_hours: '4' }),
      makeAllocation({ project_id: 'p2', allocation_hours: '16' }),
    ]

    render(<CapacityPriorityMatrixChart items={items} allocations={allocations} />)

    expect(
      screen.getByText(/Reference lines mark the median capacity/),
    ).toBeInTheDocument()
    expect(screen.getByText(/2 plotted projects/)).toBeInTheDocument()
  })

  it('discloses excluded projects with a reason and a count', () => {
    const items = [
      makePortfolioRankingEntry({ project_id: 'plottable', project_name: 'Plottable', score: '10' }),
      makePortfolioRankingEntry({ project_id: 'no-alloc', project_name: 'No Allocations', score: '20' }),
      makePortfolioRankingEntry({ project_id: 'no-score', project_name: 'No Score', score: null }),
    ]
    const allocations = [
      makeAllocation({ project_id: 'plottable', allocation_hours: '5' }),
      makeAllocation({ project_id: 'no-score', allocation_hours: '5' }),
    ]

    render(<CapacityPriorityMatrixChart items={items} allocations={allocations} />)

    expect(screen.getByText(/2 projects/)).toBeInTheDocument()
    expect(screen.getByText(/No Allocations/)).toBeInTheDocument()
    expect(screen.getByText(/No Score/)).toBeInTheDocument()
    expect(screen.getByText(/missing capacity data/)).toBeInTheDocument()
    expect(screen.getByText(/missing a priority score/)).toBeInTheDocument()
  })

  it('does not disclose an exclusion note when every project is plottable', () => {
    const items = [makePortfolioRankingEntry({ project_id: 'p1', score: '10' })]
    const allocations = [makeAllocation({ project_id: 'p1', allocation_hours: '5' })]

    render(<CapacityPriorityMatrixChart items={items} allocations={allocations} />)

    expect(screen.queryByText(/not plotted because/)).toBeNull()
  })

  it('renders no unauthorized cross-organization data — only what it was given', () => {
    const items = [makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Org Project', score: '10' })]
    const allocations = [
      makeAllocation({ project_id: 'p1', allocation_hours: '5' }),
      // An allocation for a project outside the supplied portfolio items
      // (e.g. belonging to a project this view was never given) must never
      // surface a phantom row.
      makeAllocation({ project_id: 'unrelated-project', allocation_hours: '999' }),
    ]

    render(<CapacityPriorityMatrixChart items={items} allocations={allocations} />)

    const table = screen.getByRole('table', { name: 'Capacity vs. priority matrix' })
    expect(within(table).getAllByRole('row')).toHaveLength(2) // header + one project row
    expect(screen.queryByText('999')).toBeNull()
  })
})

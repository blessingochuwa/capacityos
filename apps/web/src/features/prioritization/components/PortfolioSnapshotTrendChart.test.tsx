import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PortfolioSnapshotTrendChart } from './PortfolioSnapshotTrendChart'
import { makePortfolioRankingEntry, makePortfolioSnapshot } from '@/test/fixtures'

describe('PortfolioSnapshotTrendChart', () => {
  it('prompts to select at least 2 snapshots before any trend is shown', () => {
    const snapshots = [
      makePortfolioSnapshot({ id: 'snap-1' }),
      makePortfolioSnapshot({ id: 'snap-2' }),
    ]
    render(<PortfolioSnapshotTrendChart snapshots={snapshots} />)
    expect(screen.getByText('Select at least 2 snapshots above to see a trend.')).toBeInTheDocument()
  })

  it('renders the trend table with per-snapshot scores once 2 snapshots are selected', async () => {
    const user = userEvent.setup()
    const snapshots = [
      makePortfolioSnapshot({
        id: 'snap-1',
        taken_at: '2026-08-01T00:00:00Z',
        entries: [makePortfolioRankingEntry({ project_id: 'p1', score: '400.00' })],
      }),
      makePortfolioSnapshot({
        id: 'snap-2',
        taken_at: '2026-08-15T00:00:00Z',
        entries: [makePortfolioRankingEntry({ project_id: 'p1', score: '900.00' })],
      }),
    ]
    render(<PortfolioSnapshotTrendChart snapshots={snapshots} />)

    const checkboxes = screen.getAllByRole('checkbox')
    await user.click(checkboxes[0])
    await user.click(checkboxes[1])

    expect(screen.getByText('400')).toBeInTheDocument()
    expect(screen.getByText('900')).toBeInTheDocument()
    expect(screen.getAllByText('Website Redesign').length).toBeGreaterThan(0)
  })

  it('shows an explanatory empty state when the selected snapshots have no numeric score', async () => {
    const user = userEvent.setup()
    const snapshots = [
      makePortfolioSnapshot({
        id: 'snap-1',
        framework_type: 'moscow',
        entries: [makePortfolioRankingEntry({ score: null, category: 'must' })],
      }),
      makePortfolioSnapshot({
        id: 'snap-2',
        framework_type: 'moscow',
        entries: [makePortfolioRankingEntry({ score: null, category: 'should' })],
      }),
    ]
    render(<PortfolioSnapshotTrendChart snapshots={snapshots} />)

    const checkboxes = screen.getAllByRole('checkbox')
    await user.click(checkboxes[0])
    await user.click(checkboxes[1])

    expect(
      screen.getByText('None of the selected snapshots have a numeric score to trend.'),
    ).toBeInTheDocument()
  })
})

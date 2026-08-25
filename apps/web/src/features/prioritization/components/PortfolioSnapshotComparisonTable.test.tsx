import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PortfolioSnapshotComparisonTable } from './PortfolioSnapshotComparisonTable'
import { makeSnapshotComparisonItem } from '@/test/fixtures'

describe('PortfolioSnapshotComparisonTable', () => {
  it('renders an unchanged project with its rank and score on both sides', () => {
    const item = makeSnapshotComparisonItem({ status: 'unchanged', rank_from: 1, rank_to: 1 })
    render(<PortfolioSnapshotComparisonTable items={[item]} />)
    expect(screen.getByText('Website Redesign')).toBeInTheDocument()
    expect(screen.getByText('No change')).toBeInTheDocument()
  })

  it('shows a dash for the missing side of an entered project', () => {
    const item = makeSnapshotComparisonItem({
      status: 'entered',
      rank_from: null,
      rank_to: 1,
      score_from: null,
    })
    render(<PortfolioSnapshotComparisonTable items={[item]} />)
    expect(screen.getByText('Entered')).toBeInTheDocument()
    const row = screen.getByText('Website Redesign').closest('tr')
    expect(row).not.toBeNull()
    expect(row?.textContent).toContain('—')
  })

  it('shows a dash for the missing side of a project that left', () => {
    const item = makeSnapshotComparisonItem({
      status: 'left',
      rank_from: 2,
      rank_to: null,
      score_to: null,
    })
    render(<PortfolioSnapshotComparisonTable items={[item]} />)
    expect(screen.getByText('Left')).toBeInTheDocument()
  })

  it('shows a Changed badge for a project whose rank differs', () => {
    const item = makeSnapshotComparisonItem({ status: 'changed', rank_from: 3, rank_to: 1 })
    render(<PortfolioSnapshotComparisonTable items={[item]} />)
    expect(screen.getByText('Changed')).toBeInTheDocument()
  })

  it('renders a MoSCoW category instead of a numeric score when present', () => {
    const item = makeSnapshotComparisonItem({
      status: 'changed',
      score_from: null,
      score_to: null,
      category_from: 'could',
      category_to: 'must',
    })
    render(<PortfolioSnapshotComparisonTable items={[item]} />)
    expect(screen.getByText('Could')).toBeInTheDocument()
    expect(screen.getByText('Must')).toBeInTheDocument()
  })
})

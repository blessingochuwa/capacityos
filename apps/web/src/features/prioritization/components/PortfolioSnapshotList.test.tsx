import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PortfolioSnapshotList } from './PortfolioSnapshotList'
import { makePortfolioSnapshot } from '@/test/fixtures'

describe('PortfolioSnapshotList', () => {
  it('renders one row per snapshot with its taken-at time and entry count', () => {
    const snapshot = makePortfolioSnapshot({
      id: 'snapshot-1',
      taken_at: '2026-08-25T12:00:00Z',
      entries: [
        { ...makePortfolioSnapshot().entries[0], project_id: 'a' },
        { ...makePortfolioSnapshot().entries[0], project_id: 'b' },
      ],
    })
    render(
      <PortfolioSnapshotList snapshots={[snapshot]} selectedId={undefined} onSelect={vi.fn()} />,
    )
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View' })).toBeInTheDocument()
  })

  it('calls onSelect with the snapshot id when View is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    const snapshot = makePortfolioSnapshot({ id: 'snapshot-42' })
    render(
      <PortfolioSnapshotList snapshots={[snapshot]} selectedId={undefined} onSelect={onSelect} />,
    )

    await user.click(screen.getByRole('button', { name: 'View' }))
    expect(onSelect).toHaveBeenCalledWith('snapshot-42')
  })

  it('shows "Viewing" instead of "View" for the selected snapshot', () => {
    const snapshot = makePortfolioSnapshot({ id: 'snapshot-1' })
    render(
      <PortfolioSnapshotList
        snapshots={[snapshot]}
        selectedId="snapshot-1"
        onSelect={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'Viewing' })).toBeInTheDocument()
  })
})

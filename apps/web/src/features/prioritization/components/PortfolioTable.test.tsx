import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PortfolioTable } from './PortfolioTable'
import { makePortfolioRankingEntry } from '@/test/fixtures'

describe('PortfolioTable', () => {
  it('renders a ranked project with its rank and score', () => {
    const entry = makePortfolioRankingEntry({
      project_name: 'Website Redesign',
      score: '400.00',
      rank: 1,
    })
    render(<PortfolioTable items={[entry]} />)
    expect(screen.getByText('Website Redesign')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('400.00')).toBeInTheDocument()
    expect(screen.getByText('Complete')).toBeInTheDocument()
  })

  it('shows an unranked dash and missing criteria for an incomplete score', () => {
    const entry = makePortfolioRankingEntry({
      project_name: 'Incomplete Project',
      score: null,
      rank: null,
      missing_criteria: ['effort'],
    })
    render(<PortfolioTable items={[entry]} />)
    expect(screen.getByText('Missing effort')).toBeInTheDocument()
    const row = screen.getByText('Incomplete Project').closest('tr')
    expect(row).not.toBeNull()
    expect(row?.textContent).toContain('—')
  })

  it('calls onSelectProject with the project id when a project name is clicked', async () => {
    const user = userEvent.setup()
    const onSelectProject = vi.fn()
    const entry = makePortfolioRankingEntry({ project_id: 'project-42' })
    render(<PortfolioTable items={[entry]} onSelectProject={onSelectProject} />)

    await user.click(screen.getByRole('button', { name: entry.project_name }))
    expect(onSelectProject).toHaveBeenCalledWith('project-42')
  })

  it('renders project names as plain text, not buttons, when onSelectProject is omitted', () => {
    const entry = makePortfolioRankingEntry()
    render(<PortfolioTable items={[entry]} />)
    expect(screen.queryByRole('button', { name: entry.project_name })).not.toBeInTheDocument()
    expect(screen.getByText(entry.project_name)).toBeInTheDocument()
  })
})

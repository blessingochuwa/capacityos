import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { RiskValueMatrixChart } from './RiskValueMatrixChart'
import { useRisksForProjects } from '../hooks/useRisksForProjects'
import { makePortfolioRankingEntry, makeProjectRisk } from '@/test/fixtures'
import type { Risk } from '@/features/risks/types/risks'

vi.mock('../hooks/useRisksForProjects')

const mockedUseRisksForProjects = vi.mocked(useRisksForProjects)

function pendingResult() {
  return { isPending: true, isSuccess: false, isError: false, data: undefined, error: null }
}

function successResult(data: Risk[]) {
  return { isPending: false, isSuccess: true, isError: false, data, error: null }
}

describe('RiskValueMatrixChart', () => {
  it('shows the loading state while any project risk query is pending', () => {
    const items = [makePortfolioRankingEntry({ project_id: 'p1', score: '90' })]
    mockedUseRisksForProjects.mockReturnValue([pendingResult()] as never)

    render(<RiskValueMatrixChart items={items} />)

    expect(screen.getByText('Loading risk data…')).toBeInTheDocument()
  })

  it('shows an explanatory empty state when no project has both a priority score and risk data', () => {
    mockedUseRisksForProjects.mockReturnValue([] as never)
    render(<RiskValueMatrixChart items={[]} />)

    expect(
      screen.getByText(
        'No projects have both a priority score and available risk data to plot yet.',
      ),
    ).toBeInTheDocument()
  })

  it('renders a valid project as a row with risk count, value, and quadrant', () => {
    const items = [
      makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Website Redesign', score: '90' }),
    ]
    mockedUseRisksForProjects.mockReturnValue([
      successResult([
        makeProjectRisk({ status: 'open', exposure: 'high' }),
        makeProjectRisk({ id: 'r2', status: 'open', exposure: 'high' }),
      ]),
    ] as never)

    render(<RiskValueMatrixChart items={items} />)

    const table = screen.getByRole('table', { name: 'Risk vs. value matrix' })
    const row = within(table).getByText('Website Redesign').closest('tr')
    expect(row?.textContent).toContain('2')
    expect(row?.textContent).toContain('90')
    expect(row?.textContent).toContain('Low Value / Low Risk')
  })

  it('plots a project with zero open high-exposure risks as a real point, not excluded', () => {
    const items = [makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Calm Project', score: '10' })]
    mockedUseRisksForProjects.mockReturnValue([successResult([])] as never)

    render(<RiskValueMatrixChart items={items} />)

    const table = screen.getByRole('table', { name: 'Risk vs. value matrix' })
    const row = within(table).getByText('Calm Project').closest('tr')
    expect(row?.textContent).toContain('0')
    expect(screen.queryByText(/not plotted because/)).toBeNull()
  })

  it('does not count a closed high-exposure risk toward the plotted risk value', () => {
    const items = [makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Closed Risk Project', score: '10' })]
    mockedUseRisksForProjects.mockReturnValue([
      successResult([makeProjectRisk({ status: 'closed', exposure: 'high' })]),
    ] as never)

    render(<RiskValueMatrixChart items={items} />)

    const table = screen.getByRole('table', { name: 'Risk vs. value matrix' })
    const row = within(table).getByText('Closed Risk Project').closest('tr')
    expect(row?.textContent).toContain('0')
  })

  it('excludes a project whose risk data failed to load, disclosing the reason', () => {
    const items = [
      makePortfolioRankingEntry({ project_id: 'ok', project_name: 'Has Risk Data', score: '50' }),
      makePortfolioRankingEntry({ project_id: 'broken', project_name: 'No Risk Data', score: '60' }),
    ]
    mockedUseRisksForProjects.mockReturnValue([
      successResult([]),
      { isPending: false, isSuccess: false, isError: true, data: undefined, error: new Error('failed') },
    ] as never)

    render(<RiskValueMatrixChart items={items} />)

    const table = screen.getByRole('table', { name: 'Risk vs. value matrix' })
    expect(within(table).getByText('Has Risk Data')).toBeInTheDocument()
    expect(within(table).queryByText('No Risk Data')).toBeNull()
    expect(screen.getByText(/No Risk Data \(risk data could not be loaded\)/)).toBeInTheDocument()
  })

  it('excludes a project missing a priority score, disclosing the reason', () => {
    const items = [
      makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Scored Project', score: '50' }),
      makePortfolioRankingEntry({ project_id: 'p2', project_name: 'Unscored Project', score: null }),
    ]
    mockedUseRisksForProjects.mockReturnValue([successResult([]), successResult([])] as never)

    render(<RiskValueMatrixChart items={items} />)

    expect(screen.getByText(/Unscored Project \(missing a priority score\)/)).toBeInTheDocument()
  })

  it('renders all four quadrant labels and descriptions', () => {
    const items = [
      makePortfolioRankingEntry({ project_id: 'low', project_name: 'Low/Low', score: '10' }),
      makePortfolioRankingEntry({ project_id: 'high', project_name: 'High/High', score: '90' }),
    ]
    mockedUseRisksForProjects.mockReturnValue([
      successResult([]),
      successResult([
        makeProjectRisk({ status: 'open', exposure: 'high' }),
        makeProjectRisk({ id: 'r2', status: 'open', exposure: 'high' }),
      ]),
    ] as never)

    render(<RiskValueMatrixChart items={items} />)

    // "High Value / High Risk" and "Low Value / Low Risk" each appear
    // twice (once in the legend, once in the matching table row); the
    // other two appear once (legend only, no row has that quadrant).
    expect(screen.getAllByText('High Value / High Risk').length).toBeGreaterThan(0)
    expect(screen.getByText('High Value / Low Risk')).toBeInTheDocument()
    expect(screen.getByText('Low Value / High Risk')).toBeInTheDocument()
    expect(screen.getAllByText('Low Value / Low Risk').length).toBeGreaterThan(0)
  })

  it('describes the median reference lines as text, not only as chart position', () => {
    const items = [
      makePortfolioRankingEntry({ project_id: 'p1', score: '10' }),
      makePortfolioRankingEntry({ project_id: 'p2', score: '30' }),
    ]
    mockedUseRisksForProjects.mockReturnValue([successResult([]), successResult([])] as never)

    render(<RiskValueMatrixChart items={items} />)

    expect(screen.getByText(/Reference lines mark the median risk/)).toBeInTheDocument()
    expect(screen.getByText(/2 plotted projects/)).toBeInTheDocument()
  })

  it('does not disclose an exclusion note when every project is plottable', () => {
    const items = [makePortfolioRankingEntry({ project_id: 'p1', score: '10' })]
    mockedUseRisksForProjects.mockReturnValue([successResult([])] as never)

    render(<RiskValueMatrixChart items={items} />)

    expect(screen.queryByText(/not plotted because/)).toBeNull()
  })
})

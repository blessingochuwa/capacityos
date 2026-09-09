import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { OrgRiskRegisterTable } from './OrgRiskRegisterTable'
import { makeProjectRisk } from '@/test/fixtures'

describe('OrgRiskRegisterTable', () => {
  it('shows an empty state when there are no risks at all', () => {
    render(<OrgRiskRegisterTable risks={[]} projectLabels={new Map()} personLabels={new Map()} />)
    expect(screen.getByText('No risks recorded in this organization yet.')).toBeInTheDocument()
  })

  it('shows a distinct empty state when filters exclude every risk', () => {
    render(
      <OrgRiskRegisterTable
        risks={[]}
        projectLabels={new Map()}
        personLabels={new Map()}
        isFiltered
      />,
    )
    expect(screen.getByText('No risks match these filters.')).toBeInTheDocument()
    expect(screen.queryByText('No risks recorded in this organization yet.')).not.toBeInTheDocument()
  })

  it('renders a risk with its project name, exposure, owner, status, and review date', () => {
    const risk = makeProjectRisk({
      project_id: 'project-1',
      description: 'Vendor may miss the deadline',
      exposure: 'high',
      owner_person_id: 'person-1',
      status: 'open',
      review_date: '2026-10-01',
    })

    render(
      <OrgRiskRegisterTable
        risks={[risk]}
        projectLabels={new Map([['project-1', 'Website Redesign']])}
        personLabels={new Map([['person-1', 'Ada Lovelace']])}
      />,
    )

    const table = screen.getByRole('table', {
      name: 'Every risk across every project in this organization',
    })
    const row = within(table).getByText('Vendor may miss the deadline').closest('tr')
    expect(row?.textContent).toContain('Website Redesign')
    expect(row?.textContent).toContain('High')
    expect(row?.textContent).toContain('Ada Lovelace')
    expect(row?.textContent).toContain('Open')
    expect(row?.textContent).toContain('2026-10-01')
  })

  it('shows a fallback for a project not present in the lookup map', () => {
    const risk = makeProjectRisk({ project_id: 'unknown-project' })
    render(
      <OrgRiskRegisterTable risks={[risk]} projectLabels={new Map()} personLabels={new Map()} />,
    )

    expect(screen.getByText('Unknown project')).toBeInTheDocument()
  })

  it('shows "Unassigned" when a risk has no owner', () => {
    const risk = makeProjectRisk({ project_id: 'project-1', owner_person_id: null })
    render(
      <OrgRiskRegisterTable
        risks={[risk]}
        projectLabels={new Map([['project-1', 'Website Redesign']])}
        personLabels={new Map()}
      />,
    )

    expect(screen.getByText('Unassigned')).toBeInTheDocument()
  })

  it('renders multiple risks across different projects as separate rows', () => {
    const risks = [
      makeProjectRisk({ id: 'r1', project_id: 'p1', description: 'Risk on A' }),
      makeProjectRisk({ id: 'r2', project_id: 'p2', description: 'Risk on B' }),
    ]
    render(
      <OrgRiskRegisterTable
        risks={risks}
        projectLabels={
          new Map([
            ['p1', 'Project A'],
            ['p2', 'Project B'],
          ])
        }
        personLabels={new Map()}
      />,
    )

    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(3) // header + 2
    expect(screen.getByText('Project A')).toBeInTheDocument()
    expect(screen.getByText('Project B')).toBeInTheDocument()
  })
})

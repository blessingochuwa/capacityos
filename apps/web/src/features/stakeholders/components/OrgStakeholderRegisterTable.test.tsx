import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { makeStakeholder } from '@/test/fixtures'
import { OrgStakeholderRegisterTable } from './OrgStakeholderRegisterTable'

describe('OrgStakeholderRegisterTable', () => {
  it('shows the "nothing recorded" empty state when unfiltered', () => {
    render(
      <OrgStakeholderRegisterTable
        stakeholders={[]}
        projectLabels={new Map()}
        personLabels={new Map()}
      />,
    )
    expect(
      screen.getByText('No stakeholders recorded in this organization yet.'),
    ).toBeInTheDocument()
  })

  it('shows a distinct "no match" empty state when filtered', () => {
    render(
      <OrgStakeholderRegisterTable
        stakeholders={[]}
        projectLabels={new Map()}
        personLabels={new Map()}
        isFiltered
      />,
    )
    expect(screen.getByText('No stakeholders match these filters.')).toBeInTheDocument()
    expect(
      screen.queryByText('No stakeholders recorded in this organization yet.'),
    ).not.toBeInTheDocument()
  })

  it('renders each stakeholder with its project name and every recorded field', () => {
    const stakeholder = makeStakeholder({
      project_id: 'project-1',
      name: 'Jordan Client',
      person_id: 'person-1',
      role: 'Sponsor',
      influence: 'high',
      interest: 'low',
      decision_authority: 'decision_maker',
      communication_needs: 'Weekly email summary',
    })

    render(
      <OrgStakeholderRegisterTable
        stakeholders={[stakeholder]}
        projectLabels={new Map([['project-1', 'Website Redesign']])}
        personLabels={new Map([['person-1', 'Ada Lovelace']])}
      />,
    )

    const row = screen.getAllByRole('row')[1]
    expect(within(row).getByText('Website Redesign')).toBeInTheDocument()
    expect(within(row).getByText('Jordan Client')).toBeInTheDocument()
    expect(within(row).getByText('Linked to Ada Lovelace')).toBeInTheDocument()
    expect(within(row).getByText('Weekly email summary')).toBeInTheDocument()
    expect(within(row).getByText('Sponsor')).toBeInTheDocument()
    expect(within(row).getByText('High')).toBeInTheDocument()
    expect(within(row).getByText('Low')).toBeInTheDocument()
    expect(within(row).getByText('Decision maker')).toBeInTheDocument()
  })

  it('falls back to a placeholder when the project name is not yet known', () => {
    render(
      <OrgStakeholderRegisterTable
        stakeholders={[makeStakeholder({ project_id: 'unknown' })]}
        projectLabels={new Map()}
        personLabels={new Map()}
      />,
    )
    expect(screen.getByText('Unknown project')).toBeInTheDocument()
  })

  it('is read-only — no edit or remove controls', () => {
    render(
      <OrgStakeholderRegisterTable
        stakeholders={[makeStakeholder()]}
        projectLabels={new Map()}
        personLabels={new Map()}
      />,
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})

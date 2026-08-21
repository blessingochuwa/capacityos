import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StakeholdersTable } from './StakeholdersTable'
import { makeStakeholder } from '@/test/fixtures'

describe('StakeholdersTable', () => {
  it('renders an empty state when no stakeholders are recorded', () => {
    render(
      <StakeholdersTable
        stakeholders={[]}
        personLabels={new Map()}
        onEdit={() => {}}
        onRemove={() => {}}
      />,
    )
    expect(
      screen.getByText('No stakeholders recorded for this project yet.'),
    ).toBeInTheDocument()
  })

  it('renders a stakeholder with its name, role, influence, and interest', () => {
    const stakeholder = makeStakeholder({
      name: 'Jordan Client',
      role: 'Sponsor',
      influence: 'high',
      interest: 'low',
    })
    render(
      <StakeholdersTable
        stakeholders={[stakeholder]}
        personLabels={new Map()}
        onEdit={() => {}}
        onRemove={() => {}}
      />,
    )
    expect(screen.getByText('Jordan Client')).toBeInTheDocument()
    expect(screen.getByText('Sponsor')).toBeInTheDocument()
    expect(screen.getByText('High')).toBeInTheDocument()
    expect(screen.getByText('Low')).toBeInTheDocument()
  })

  it('shows the linked person label when person_id is set', () => {
    const stakeholder = makeStakeholder({ person_id: 'person-1' })
    render(
      <StakeholdersTable
        stakeholders={[stakeholder]}
        personLabels={new Map([['person-1', 'Alex Morgan']])}
        onEdit={() => {}}
        onRemove={() => {}}
      />,
    )
    expect(screen.getByText('Linked to Alex Morgan')).toBeInTheDocument()
  })

  it('calls onEdit with the stakeholder id when Edit is clicked', async () => {
    const user = userEvent.setup()
    const stakeholder = makeStakeholder()
    const onEdit = vi.fn()
    render(
      <StakeholdersTable
        stakeholders={[stakeholder]}
        personLabels={new Map()}
        onEdit={onEdit}
        onRemove={() => {}}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Edit' }))
    expect(onEdit).toHaveBeenCalledWith(stakeholder.id)
  })

  it('calls onRemove with the stakeholder id when Remove is clicked', async () => {
    const user = userEvent.setup()
    const stakeholder = makeStakeholder()
    const onRemove = vi.fn()
    render(
      <StakeholdersTable
        stakeholders={[stakeholder]}
        personLabels={new Map()}
        onEdit={() => {}}
        onRemove={onRemove}
      />,
    )
    await user.click(screen.getByRole('button', { name: /remove/i }))
    expect(onRemove).toHaveBeenCalledWith(stakeholder.id)
  })

  it('hides Edit and Remove buttons when canManage is false', () => {
    const stakeholder = makeStakeholder()
    render(
      <StakeholdersTable
        stakeholders={[stakeholder]}
        personLabels={new Map()}
        onEdit={() => {}}
        onRemove={() => {}}
        canManage={false}
      />,
    )
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument()
  })
})

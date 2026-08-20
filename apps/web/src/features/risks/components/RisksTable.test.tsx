import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RisksTable } from './RisksTable'
import { makeProjectRisk } from '@/test/fixtures'

describe('RisksTable', () => {
  it('renders an empty state when no risks are recorded', () => {
    render(
      <RisksTable
        risks={[]}
        personLabels={new Map()}
        onStatusChange={() => {}}
        onRemove={() => {}}
      />,
    )
    expect(screen.getByText('No risks recorded for this project yet.')).toBeInTheDocument()
  })

  it('renders a risk with its description, exposure, and status', () => {
    const risk = makeProjectRisk({ description: 'Vendor delay', exposure: 'high', status: 'open' })
    render(
      <RisksTable
        risks={[risk]}
        personLabels={new Map()}
        onStatusChange={() => {}}
        onRemove={() => {}}
      />,
    )
    expect(screen.getByText('Vendor delay')).toBeInTheDocument()
    expect(screen.getByText('High')).toBeInTheDocument()
  })

  it('shows "Unassigned" when a risk has no owner', () => {
    const risk = makeProjectRisk({ owner_person_id: null })
    render(
      <RisksTable
        risks={[risk]}
        personLabels={new Map()}
        onStatusChange={() => {}}
        onRemove={() => {}}
      />,
    )
    expect(screen.getByText('Unassigned')).toBeInTheDocument()
  })

  it('resolves the owner label from personLabels when set', () => {
    const risk = makeProjectRisk({ owner_person_id: 'person-1' })
    render(
      <RisksTable
        risks={[risk]}
        personLabels={new Map([['person-1', 'Jane Doe']])}
        onStatusChange={() => {}}
        onRemove={() => {}}
      />,
    )
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
  })

  it('calls onStatusChange when the status select changes', async () => {
    const user = userEvent.setup()
    const risk = makeProjectRisk({ status: 'open' })
    const onStatusChange = vi.fn()
    render(
      <RisksTable
        risks={[risk]}
        personLabels={new Map()}
        onStatusChange={onStatusChange}
        onRemove={() => {}}
      />,
    )
    await user.selectOptions(screen.getByRole('combobox'), 'mitigating')
    expect(onStatusChange).toHaveBeenCalledWith(risk.id, 'mitigating')
  })

  it('calls onRemove with the risk id when Remove is clicked', async () => {
    const user = userEvent.setup()
    const risk = makeProjectRisk()
    const onRemove = vi.fn()
    render(
      <RisksTable
        risks={[risk]}
        personLabels={new Map()}
        onStatusChange={() => {}}
        onRemove={onRemove}
      />,
    )
    await user.click(screen.getByRole('button', { name: /remove/i }))
    expect(onRemove).toHaveBeenCalledWith(risk.id)
  })

  it('hides the status control and remove button when canManage is false', () => {
    const risk = makeProjectRisk({ status: 'open' })
    render(
      <RisksTable
        risks={[risk]}
        personLabels={new Map()}
        onStatusChange={() => {}}
        onRemove={() => {}}
        canManage={false}
      />,
    )
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument()
    expect(screen.getByText('Open')).toBeInTheDocument()
  })
})

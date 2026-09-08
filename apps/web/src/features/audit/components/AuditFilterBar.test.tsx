import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuditFilterBar } from './AuditFilterBar'

function defaultProps() {
  return {
    actorOptions: [] as { value: string; label: string }[],
    actorValue: '',
    onActorChange: vi.fn(),
    actionValue: '',
    onActionChange: vi.fn(),
    resourceTypeValue: '',
    onResourceTypeChange: vi.fn(),
    startValue: '',
    onStartChange: vi.fn(),
    endValue: '',
    onEndChange: vi.fn(),
  }
}

describe('AuditFilterBar', () => {
  it('renders actor, action, resource type, since, and until controls', () => {
    render(<AuditFilterBar {...defaultProps()} />)

    expect(screen.getByLabelText('Actor')).toBeInTheDocument()
    expect(screen.getByLabelText('Action')).toBeInTheDocument()
    expect(screen.getByLabelText('Resource type')).toBeInTheDocument()
    expect(screen.getByLabelText('Since')).toBeInTheDocument()
    expect(screen.getByLabelText('Until')).toBeInTheDocument()
  })

  it('lists the supplied actor options', () => {
    render(
      <AuditFilterBar
        {...defaultProps()}
        actorOptions={[
          { value: 'user-1', label: 'Ada Lovelace (ada@acme.test)' },
          { value: 'user-2', label: 'Alan Turing (alan@acme.test)' },
        ]}
      />,
    )

    const select = screen.getByLabelText('Actor')
    expect(select).toHaveTextContent('Ada Lovelace (ada@acme.test)')
    expect(select).toHaveTextContent('Alan Turing (alan@acme.test)')
  })

  it('calls onActorChange when a different actor is selected', async () => {
    const onActorChange = vi.fn()
    const user = userEvent.setup()
    render(
      <AuditFilterBar
        {...defaultProps()}
        actorOptions={[{ value: 'user-1', label: 'Ada Lovelace (ada@acme.test)' }]}
        onActorChange={onActorChange}
      />,
    )

    await user.selectOptions(screen.getByLabelText('Actor'), 'user-1')
    expect(onActorChange).toHaveBeenCalledWith('user-1')
  })

  it('calls onStartChange and onEndChange when the date fields change', () => {
    const onStartChange = vi.fn()
    const onEndChange = vi.fn()
    render(
      <AuditFilterBar {...defaultProps()} onStartChange={onStartChange} onEndChange={onEndChange} />,
    )

    // fireEvent.change (rather than userEvent's per-character typing,
    // which datetime-local inputs don't support reliably in jsdom) sets
    // the value and fires React's change handler in one step.
    fireEvent.change(screen.getByLabelText('Since'), {
      target: { value: '2026-01-15T09:30' },
    })
    fireEvent.change(screen.getByLabelText('Until'), {
      target: { value: '2026-01-20T00:00' },
    })

    expect(onStartChange).toHaveBeenCalledWith('2026-01-15T09:30')
    expect(onEndChange).toHaveBeenCalledWith('2026-01-20T00:00')
  })

  it('calls onActionChange as the Action field is typed', async () => {
    const onActionChange = vi.fn()
    const user = userEvent.setup()
    render(<AuditFilterBar {...defaultProps()} onActionChange={onActionChange} />)

    await user.type(screen.getByLabelText('Action'), 'x')
    expect(onActionChange).toHaveBeenCalledWith('x')
  })

  it('calls onResourceTypeChange as the Resource type field is typed', async () => {
    const onResourceTypeChange = vi.fn()
    const user = userEvent.setup()
    render(
      <AuditFilterBar {...defaultProps()} onResourceTypeChange={onResourceTypeChange} />,
    )

    await user.type(screen.getByLabelText('Resource type'), 'x')
    expect(onResourceTypeChange).toHaveBeenCalledWith('x')
  })

  it('reflects the current Action and Resource type values', () => {
    render(
      <AuditFilterBar
        {...defaultProps()}
        actionValue="person.create"
        resourceTypeValue="person"
      />,
    )

    expect(screen.getByLabelText('Action')).toHaveValue('person.create')
    expect(screen.getByLabelText('Resource type')).toHaveValue('person')
  })

  it('does not suggest a finite taxonomy — Action and Resource type are plain text inputs, not selects', () => {
    render(<AuditFilterBar {...defaultProps()} />)

    expect(screen.getByLabelText('Action').tagName).toBe('INPUT')
    expect(screen.getByLabelText('Resource type').tagName).toBe('INPUT')
  })
})

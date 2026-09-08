import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuditFilterBar } from './AuditFilterBar'

describe('AuditFilterBar', () => {
  it('renders actor, since, and until controls', () => {
    render(
      <AuditFilterBar
        actorOptions={[]}
        actorValue=""
        onActorChange={vi.fn()}
        startValue=""
        onStartChange={vi.fn()}
        endValue=""
        onEndChange={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Actor')).toBeInTheDocument()
    expect(screen.getByLabelText('Since')).toBeInTheDocument()
    expect(screen.getByLabelText('Until')).toBeInTheDocument()
  })

  it('lists the supplied actor options', () => {
    render(
      <AuditFilterBar
        actorOptions={[
          { value: 'user-1', label: 'Ada Lovelace (ada@acme.test)' },
          { value: 'user-2', label: 'Alan Turing (alan@acme.test)' },
        ]}
        actorValue=""
        onActorChange={vi.fn()}
        startValue=""
        onStartChange={vi.fn()}
        endValue=""
        onEndChange={vi.fn()}
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
        actorOptions={[{ value: 'user-1', label: 'Ada Lovelace (ada@acme.test)' }]}
        actorValue=""
        onActorChange={onActorChange}
        startValue=""
        onStartChange={vi.fn()}
        endValue=""
        onEndChange={vi.fn()}
      />,
    )

    await user.selectOptions(screen.getByLabelText('Actor'), 'user-1')
    expect(onActorChange).toHaveBeenCalledWith('user-1')
  })

  it('calls onStartChange and onEndChange when the date fields change', () => {
    const onStartChange = vi.fn()
    const onEndChange = vi.fn()
    render(
      <AuditFilterBar
        actorOptions={[]}
        actorValue=""
        onActorChange={vi.fn()}
        startValue=""
        onStartChange={onStartChange}
        endValue=""
        onEndChange={onEndChange}
      />,
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
})

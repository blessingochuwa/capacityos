import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { AuditEventsTable } from './AuditEventsTable'
import { makeAuditEvent } from '@/test/fixtures'

describe('AuditEventsTable', () => {
  it('shows an empty state when there are no audit events', () => {
    render(<AuditEventsTable events={[]} />)
    expect(screen.getByText('No audit events yet.')).toBeInTheDocument()
  })

  it('shows a distinct empty state when a filter excludes every event', () => {
    render(<AuditEventsTable events={[]} isFiltered />)
    expect(screen.getByText('No audit events match these filters.')).toBeInTheDocument()
    expect(screen.queryByText('No audit events yet.')).not.toBeInTheDocument()
  })

  it('renders timestamp, actor, action, outcome, and target for an event', () => {
    const event = makeAuditEvent({
      timestamp: '2026-01-15T09:30:00Z',
      actor_email: 'ada@acme.test',
      action: 'person.create',
      outcome: 'success',
      resource_type: 'person',
      resource_id: 'person-42',
    })
    render(<AuditEventsTable events={[event]} />)

    const table = screen.getByRole('table', {
      name: 'Audit events for this organization, most recent first',
    })
    const row = within(table).getByText('ada@acme.test').closest('tr')
    expect(row).not.toBeNull()
    expect(row?.textContent).toContain('2026')
    expect(row?.textContent).toContain('person.create')
    expect(row?.textContent).toContain('Success')
    expect(row?.textContent).toContain('person')
    expect(row?.textContent).toContain('person-42')
  })

  it('renders event_metadata details when present', () => {
    const event = makeAuditEvent({
      action: 'user.status_change',
      event_metadata: { old_status: 'active', new_status: 'disabled' },
    })
    render(<AuditEventsTable events={[event]} />)

    expect(screen.getByText('old_status: active, new_status: disabled')).toBeInTheDocument()
  })

  it('renders gracefully when actor, target, and details are all null', () => {
    const event = makeAuditEvent({
      actor_email: null,
      actor_user_id: null,
      resource_type: null,
      resource_id: null,
      event_metadata: null,
    })
    render(<AuditEventsTable events={[event]} />)

    expect(screen.getByText('Unknown actor')).toBeInTheDocument()
    const table = screen.getByRole('table')
    const dashes = within(table).getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(2) // target + details
  })

  it('renders the outcome badge for a denied event distinctly from success', () => {
    const events = [
      makeAuditEvent({ id: 'a', outcome: 'success' }),
      makeAuditEvent({ id: 'b', outcome: 'denied', action: 'permission.denied' }),
      makeAuditEvent({ id: 'c', outcome: 'failure', action: 'auth.login_failure' }),
    ]
    render(<AuditEventsTable events={events} />)

    expect(screen.getByText('Success')).toBeInTheDocument()
    expect(screen.getByText('Denied')).toBeInTheDocument()
    expect(screen.getByText('Failure')).toBeInTheDocument()
  })

  it('renders multiple events as separate rows', () => {
    const events = [
      makeAuditEvent({ id: 'a', actor_email: 'ada@acme.test' }),
      makeAuditEvent({ id: 'b', actor_email: 'alan@acme.test' }),
    ]
    render(<AuditEventsTable events={events} />)

    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(3) // header + 2
  })
})

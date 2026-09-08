import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { OUTCOME_BADGE } from '../constants'
import type { AuditEvent } from '../types/audit'

interface AuditEventsTableProps {
  events: AuditEvent[]
  /** True when an actor or date-range filter is currently applied — an
   * empty result then means "no match", not "no history exists" (mirrors
   * features/users/components/UsersTable.tsx's `isFiltered` precedent). */
  isFiltered?: boolean
}

function detailsCell(metadata: Record<string, unknown> | null) {
  if (!metadata || Object.keys(metadata).length === 0) {
    return <span className="text-slate-500">—</span>
  }
  return (
    <span className="text-xs text-slate-400">
      {Object.entries(metadata)
        .map(([key, value]) => `${key}: ${String(value)}`)
        .join(', ')}
    </span>
  )
}

function targetCell(event: AuditEvent) {
  if (!event.resource_type) return <span className="text-slate-500">—</span>
  return (
    <>
      {event.resource_type}
      {event.resource_id ? (
        <span className="block truncate text-xs text-slate-500" title={event.resource_id}>
          {event.resource_id}
        </span>
      ) : null}
    </>
  )
}

/** The audit log's event list (Phase 43) — reuses every field
 * `GET /api/v1/audit` already returns (apps/api/app/schemas/audit.py),
 * never fabricating a human-readable label for `action`/`resource_type`
 * (both are backend-owned, open vocabularies — see types/audit.ts).
 * Chart-free: an audit trail is inherently tabular, so this is a table
 * only, matching every other list-shaped page in this codebase
 * (MembersTable, UsersTable). */
export function AuditEventsTable({ events, isFiltered = false }: AuditEventsTableProps) {
  if (events.length === 0) {
    return isFiltered ? (
      <EmptyState
        title="No audit events match these filters."
        description="Try a different actor or date range."
      />
    ) : (
      <EmptyState
        title="No audit events yet."
        description="Activity in this organization — logins, permission denials, and record changes — will appear here as it happens."
      />
    )
  }

  return (
    <Table caption="Audit events for this organization, most recent first">
      <thead>
        <tr>
          <Th scope="col">Timestamp</Th>
          <Th scope="col">Actor</Th>
          <Th scope="col">Action</Th>
          <Th scope="col">Outcome</Th>
          <Th scope="col">Target</Th>
          <Th scope="col">Details</Th>
        </tr>
      </thead>
      <tbody>
        {events.map((event) => {
          const badge = OUTCOME_BADGE[event.outcome]
          return (
            <tr key={event.id}>
              <Td className="whitespace-nowrap tabular-nums">
                {new Date(event.timestamp).toLocaleString()}
              </Td>
              <Td>{event.actor_email ?? <span className="text-slate-500">Unknown actor</span>}</Td>
              <Td>
                <code className="text-xs text-slate-300">{event.action}</code>
              </Td>
              <Td>
                <Badge variant={badge.variant}>{badge.label}</Badge>
              </Td>
              <Td>{targetCell(event)}</Td>
              <Td>{detailsCell(event.event_metadata)}</Td>
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}

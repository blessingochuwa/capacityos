/**
 * Plain-language formatting for scenario operations and comparisons — pure
 * string templating over already-typed fields, never a calculation (prompt
 * §17: "Add 20 hours", not "Create allocation delta"). Reuses
 * features/capacity/utils/presentation.ts for anything capacity-shaped
 * (hours, utilization) rather than re-implementing it.
 */
import {
  formatDateRange,
  formatHours,
} from '@/features/capacity/utils/presentation'
import { toNumber } from '@/lib/decimal'
import type {
  ScenarioOperation,
  ScenarioOperationPayload,
} from '../types/scenario'

export interface NameLookup {
  personLabel: (personId: string) => string
  projectLabel: (projectId: string) => string
}

function describePayload(
  payload: ScenarioOperationPayload,
  names: NameLookup,
): string {
  switch (payload.operation_type) {
    case 'add_allocation':
      return `Add ${formatHours(payload.hours)} for ${names.personLabel(payload.person_id)} on ${names.projectLabel(payload.project_id)} (${formatDateRange(payload.start_date, payload.end_date)})`
    case 'adjust_allocation': {
      const parts: string[] = []
      if (payload.hours !== null)
        parts.push(`set hours to ${formatHours(payload.hours)}`)
      if (payload.start_date || payload.end_date) parts.push('change dates')
      return `Adjust allocation — ${parts.join(', ') || 'no change'}`
    }
    case 'remove_allocation':
      return 'Remove an allocation'
    case 'move_allocation':
      return payload.hours
        ? `Move ${formatHours(payload.hours)} to ${names.personLabel(payload.to_person_id)}`
        : `Move the whole allocation to ${names.personLabel(payload.to_person_id)}`
    case 'shift_project': {
      const days = Math.abs(payload.day_offset)
      const direction = payload.day_offset < 0 ? 'earlier' : 'later'
      return `${names.projectLabel(payload.project_id)} starts ${days} day${days === 1 ? '' : 's'} ${direction}`
    }
    case 'availability_override':
      return payload.hours === null
        ? `${names.personLabel(payload.person_id)} is unavailable ${formatDateRange(payload.start_date, payload.end_date)}`
        : `${names.personLabel(payload.person_id)} is available ${formatHours(payload.hours)}/day ${formatDateRange(payload.start_date, payload.end_date)}`
    case 'availability_clear':
      return `${names.personLabel(payload.person_id)} returns to their normal schedule ${formatDateRange(payload.start_date, payload.end_date)}`
    case 'add_hypothetical_resource':
      return `Add hypothetical "${payload.label}" — ${formatHours(payload.hours_per_week)}/week (${formatDateRange(payload.start_date, payload.end_date)})`
  }
}

export function describeOperation(
  operation: ScenarioOperation,
  names: NameLookup,
): string {
  return describePayload(operation.payload, names)
}

/** "+13pp" / "-13pp" for a utilization delta expressed as percentage points. */
export function formatUtilizationDelta(delta: string | null): string {
  if (delta === null) return '—'
  const points = Math.round(toNumber(delta) * 100)
  if (points === 0) return '0pp'
  return `${points > 0 ? '+' : ''}${points}pp`
}

/** "+6h" / "-6h" for an hours delta — sign-aware, unlike formatHours. */
export function formatHoursDelta(delta: string): string {
  const hours = toNumber(delta)
  const rounded = Math.round(hours * 10) / 10
  if (rounded === 0) return '0h'
  const magnitude = Number.isInteger(rounded)
    ? Math.abs(rounded).toFixed(0)
    : Math.abs(rounded).toFixed(1)
  return `${rounded > 0 ? '+' : '-'}${magnitude}h`
}

/** "+2" / "-2" / "0" for a plain count delta (over-allocated people, etc). */
export function formatCountDelta(delta: number): string {
  if (delta === 0) return '0'
  return delta > 0 ? `+${delta}` : `${delta}`
}

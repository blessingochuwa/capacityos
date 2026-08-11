import { toNumber } from '@/lib/decimal'
import { AT_CAPACITY_MIN } from '../constants/thresholds'

export type CapacityStatus = 'over' | 'at' | 'under' | 'no-data'

export const CAPACITY_STATUS_LABEL: Record<CapacityStatus, string> = {
  over: 'Over capacity',
  at: 'At capacity',
  under: 'Under capacity',
  'no-data': 'No capacity data',
}

/**
 * Turns already-computed backend numbers into one of 4 status buckets.
 * Precedence matters and is deliberate: over-allocation (a hard fact — see
 * app/domain/capacity.py::over_allocation) always wins, even if utilization
 * is technically undefined; null utilization (no effective capacity) is
 * reported as its own state, never coerced to "under capacity"; only then
 * does the one invented threshold (AT_CAPACITY_MIN) apply.
 */
export function getCapacityStatus(
  utilization: string | null,
  overAllocation: string,
): CapacityStatus {
  if (toNumber(overAllocation) > 0) return 'over'
  if (utilization === null) return 'no-data'
  return toNumber(utilization) >= AT_CAPACITY_MIN ? 'at' : 'under'
}

/** Whole/one-decimal hours, never false precision (spec §8: "82%", not
 * "82.376492%" — the same principle applies to hours). */
export function formatHours(value: string): string {
  const hours = toNumber(value)
  const rounded = Math.round(hours * 10) / 10
  return `${Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)}h`
}

/** null is never shown to users as "null" or "0%" — see spec §8 and
 * docs/domain-concepts.md#capacity-engine-phase-2 (zero effective capacity
 * is a different fact than zero utilization). */
export function formatUtilization(utilization: string | null): string {
  if (utilization === null) return 'No effective capacity'
  return `${Math.round(toNumber(utilization) * 100)}%`
}

/** null (rendered by formatUtilization) already explains itself; this is
 * the short supporting sentence for a tooltip/helper-text context. */
export function utilizationHelperText(utilization: string | null): string {
  if (utilization === null) {
    return 'There is no effective capacity in this period, so a utilization percentage would be misleading.'
  }
  return 'Allocated capacity ÷ effective capacity for the selected period.'
}

export function formatOverAllocation(overAllocation: string): string | null {
  const hours = toNumber(overAllocation)
  return hours > 0 ? `${formatHours(overAllocation)} over` : null
}

export function formatDateRange(startDate: string, endDate: string): string {
  const format = (iso: string) =>
    new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    })
  return startDate === endDate
    ? format(startDate)
    : `${format(startDate)} – ${format(endDate)}`
}

/** "annual_leave" -> "Annual leave" — a display label, not a new vocabulary;
 * the controlled list itself is owned by AvailabilityType (app/models/enums.py). */
export function formatAvailabilityType(availabilityType: string): string {
  const words = availabilityType.split('_')
  return `${words[0].charAt(0).toUpperCase()}${words[0].slice(1)} ${words.slice(1).join(' ')}`.trim()
}

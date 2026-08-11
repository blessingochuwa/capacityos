/**
 * Date-range construction ONLY — building query-parameter values for the
 * capacity API to evaluate. This is UI convenience, not a capacity
 * calculation (CLAUDE.md §4/§10: the engine is the only source of capacity
 * numbers); nothing here produces an hours/utilization figure.
 *
 * Monday-start matches the backend's canonical week
 * (apps/api/app/domain/dates.py::WEEK_START_WEEKDAY) — JS's Date.getDay()
 * is 0=Sunday..6=Saturday, so it needs its own conversion, done once here.
 */

export interface DateRange {
  start: string
  end: string
}

function toISODate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function startOfWeek(date: Date): Date {
  const weekday = date.getDay() // 0=Sun..6=Sat
  const diffToMonday = weekday === 0 ? -6 : 1 - weekday
  const monday = new Date(date)
  monday.setHours(0, 0, 0, 0)
  monday.setDate(monday.getDate() + diffToMonday)
  return monday
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date)
  result.setDate(result.getDate() + days)
  return result
}

export function thisWeek(today: Date = new Date()): DateRange {
  const monday = startOfWeek(today)
  return { start: toISODate(monday), end: toISODate(addDays(monday, 6)) }
}

export function nextWeek(today: Date = new Date()): DateRange {
  const monday = addDays(startOfWeek(today), 7)
  return { start: toISODate(monday), end: toISODate(addDays(monday, 6)) }
}

export function thisMonth(today: Date = new Date()): DateRange {
  const start = new Date(today.getFullYear(), today.getMonth(), 1)
  const end = new Date(today.getFullYear(), today.getMonth() + 1, 0)
  return { start: toISODate(start), end: toISODate(end) }
}

export type DateRangePreset =
  'this-week' | 'next-week' | 'this-month' | 'custom'

export const DATE_RANGE_PRESETS: ReadonlyArray<{
  id: DateRangePreset
  label: string
}> = [
  { id: 'this-week', label: 'This week' },
  { id: 'next-week', label: 'Next week' },
  { id: 'this-month', label: 'This month' },
  { id: 'custom', label: 'Custom range' },
]

/** Resolves a preset to concrete dates; returns null for 'custom', which
 * means "leave whatever start/end the user already has selected." */
export function resolvePreset(
  preset: DateRangePreset,
  today: Date = new Date(),
): DateRange | null {
  switch (preset) {
    case 'this-week':
      return thisWeek(today)
    case 'next-week':
      return nextWeek(today)
    case 'this-month':
      return thisMonth(today)
    case 'custom':
      return null
  }
}

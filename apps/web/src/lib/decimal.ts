/**
 * The one place a backend Decimal-string becomes a JS number. apps/api
 * serializes every hour quantity and utilization ratio as a string
 * (Decimal, not float — see apps/api/tests/api/test_allocations.py) so no
 * precision is lost in transit. Converting to `number` here is for
 * display/sorting/chart-axis purposes only — the result must never be fed
 * back into a capacity formula; the backend already computed the number.
 */
export function toNumber(value: string): number {
  return Number(value)
}

export function toNumberOrNull(value: string | null): number | null {
  return value === null ? null : Number(value)
}

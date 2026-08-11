import { toNumber } from '@/lib/decimal'
import { formatHours } from '../utils/presentation'

interface CapacityBarProps {
  effectiveCapacity: string
  allocatedCapacity: string
  remainingCapacity: string
  overAllocation: string
  className?: string
}

/**
 * Effective vs. allocated capacity, drawn to scale. When allocated exceeds
 * effective, the bar is NOT clipped at 100% — the track widens to fit the
 * full allocated amount and a marker line shows where effective capacity
 * ends, with the overflow rendered in a distinct color (spec §7: "the
 * visualization must clearly communicate the overflow rather than clipping
 * the bar"). Every number here (effective/allocated/remaining/over) comes
 * straight from the backend; the only math below is turning already-decided
 * facts into pixel percentages, never a new capacity decision.
 */
export function CapacityBar({
  effectiveCapacity,
  allocatedCapacity,
  remainingCapacity,
  overAllocation,
  className = '',
}: CapacityBarProps) {
  const effective = toNumber(effectiveCapacity)
  const allocated = toNumber(allocatedCapacity)
  const overAllocated = toNumber(overAllocation)

  if (effective <= 0 && allocated <= 0) {
    return (
      <div
        role="img"
        aria-label="No effective capacity in this period"
        className={`h-2 w-full rounded-full bg-slate-800 ${className}`}
      />
    )
  }

  const scale = Math.max(effective, allocated, 0.0001)
  // Guaranteed by the backend's own formula (over_allocation = max(allocated - effective, 0))
  // to equal min(allocated, effective) — not a new fact, just unpacking one.
  const withinCapacity = allocated - overAllocated
  const withinPercent = (withinCapacity / scale) * 100
  const overPercent = (overAllocated / scale) * 100
  const effectiveMarkPercent = (effective / scale) * 100

  const label =
    overAllocated > 0
      ? `${formatHours(allocatedCapacity)} of ${formatHours(effectiveCapacity)} allocated, ${formatHours(overAllocation)} over capacity`
      : `${formatHours(allocatedCapacity)} of ${formatHours(effectiveCapacity)} allocated, ${formatHours(remainingCapacity)} remaining`

  return (
    <div
      role="img"
      aria-label={label}
      className={`relative h-2 w-full rounded-full bg-slate-800 ${className}`}
    >
      <div
        className="absolute inset-y-0 left-0 rounded-l-full bg-indigo-400"
        style={{ width: `${withinPercent}%` }}
      />
      {overAllocated > 0 ? (
        <div
          className="absolute inset-y-0 rounded-r-full bg-rose-500"
          style={{ left: `${withinPercent}%`, width: `${overPercent}%` }}
        />
      ) : null}
      {overAllocated > 0 ? (
        <div
          aria-hidden="true"
          className="absolute inset-y-0 w-px bg-slate-100/80"
          style={{ left: `${effectiveMarkPercent}%` }}
        />
      ) : null}
    </div>
  )
}

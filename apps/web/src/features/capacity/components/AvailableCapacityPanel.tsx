import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/ui/EmptyState'
import { ChevronRightIcon } from '@/components/ui/icons'
import type { Person } from '@/types/entities'
import type { PersonCapacity } from '../types/capacity'
import { formatHours } from '../utils/presentation'
import { toNumber } from '@/lib/decimal'

interface AvailableCapacityPanelProps {
  members: PersonCapacity[]
  peopleLookup: Map<string, Person>
}

/** "Who has usable capacity?" (spec §11) — surfaces the fact only; no
 * automatic reassignment or "move this work" suggestion (explicitly out of
 * scope for Phase 3). */
export function AvailableCapacityPanel({
  members,
  peopleLookup,
}: AvailableCapacityPanelProps) {
  const available = members
    .filter((member) => toNumber(member.remaining_capacity) > 0)
    .sort(
      (a, b) => toNumber(b.remaining_capacity) - toNumber(a.remaining_capacity),
    )

  if (available.length === 0) {
    return (
      <EmptyState
        title="No available capacity in this period."
        description="Every team member is fully or over allocated."
      />
    )
  }

  return (
    <ul className="divide-y divide-slate-800">
      {available.map((member) => {
        const person = peopleLookup.get(member.person_id)
        return (
          <li key={member.person_id}>
            <Link
              to={`/capacity/people/${member.person_id}`}
              className="flex items-center justify-between gap-3 px-1 py-3 hover:bg-slate-800/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
            >
              <p className="text-sm font-medium text-slate-100">
                {person?.display_name ?? 'Unknown person'}
              </p>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-sm font-semibold text-emerald-300 tabular-nums">
                  {formatHours(member.remaining_capacity)} remaining
                </span>
                <ChevronRightIcon className="size-4 text-slate-500" />
              </div>
            </Link>
          </li>
        )
      })}
    </ul>
  )
}

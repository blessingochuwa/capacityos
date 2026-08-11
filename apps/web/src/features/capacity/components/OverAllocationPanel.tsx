import { Link } from 'react-router-dom'
import { EmptyState } from '@/components/ui/EmptyState'
import { ChevronRightIcon } from '@/components/ui/icons'
import type { Person } from '@/types/entities'
import type { PersonCapacity } from '../types/capacity'
import { formatHours, formatUtilization } from '../utils/presentation'
import { toNumber } from '@/lib/decimal'

interface OverAllocationPanelProps {
  members: PersonCapacity[]
  peopleLookup: Map<string, Person>
}

/** "Who needs my attention?" (spec §10) — a focused list of facts, no
 * recommendations. Project attribution isn't shown here: the team capacity
 * response doesn't break allocations down by project, and fetching every
 * over-allocated person's allocations individually here would mean one
 * request per person (spec §30 explicitly rules out N+1 requests) — that
 * detail lives on the person page, one request, when actually drilling in. */
export function OverAllocationPanel({
  members,
  peopleLookup,
}: OverAllocationPanelProps) {
  const overAllocated = members
    .filter((member) => toNumber(member.over_allocation) > 0)
    .sort((a, b) => toNumber(b.over_allocation) - toNumber(a.over_allocation))

  if (overAllocated.length === 0) {
    return (
      <EmptyState
        title="No over-allocated people in this period."
        description="Everyone on this team is within their effective capacity."
      />
    )
  }

  return (
    <ul className="divide-y divide-slate-800">
      {overAllocated.map((member) => {
        const person = peopleLookup.get(member.person_id)
        return (
          <li key={member.person_id}>
            <Link
              to={`/capacity/people/${member.person_id}`}
              className="flex items-center justify-between gap-3 px-1 py-3 hover:bg-slate-800/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
            >
              <div>
                <p className="text-sm font-medium text-slate-100">
                  {person?.display_name ?? 'Unknown person'}
                </p>
                <p className="text-xs text-slate-400">
                  {formatHours(member.effective_capacity)} effective ·{' '}
                  {formatHours(member.allocated_hours)} allocated ·{' '}
                  {formatUtilization(member.utilization)} utilized
                </p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-sm font-semibold text-rose-300 tabular-nums">
                  {formatHours(member.over_allocation)} over
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

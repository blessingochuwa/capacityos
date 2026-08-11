import { Link } from 'react-router-dom'
import { Table, Td, Th } from '@/components/ui/Table'
import { EmptyState } from '@/components/ui/EmptyState'
import type { Person } from '@/types/entities'
import type { PersonCapacity } from '../types/capacity'
import { CapacityBar } from './CapacityBar'
import { StatusBadge } from './StatusBadge'
import {
  formatHours,
  formatUtilization,
  getCapacityStatus,
} from '../utils/presentation'

interface TeamCapacityTableProps {
  members: PersonCapacity[]
  peopleLookup: Map<string, Person>
}

/** The person-by-person roster (spec §6). Sorted so the people who most
 * need attention — over-allocated first, then highest utilization — surface
 * at the top without the user having to hunt for them. */
export function TeamCapacityTable({
  members,
  peopleLookup,
}: TeamCapacityTableProps) {
  if (members.length === 0) {
    return (
      <EmptyState
        title="No team members match this filter."
        description="Add people to this team or choose a different team to see their capacity."
      />
    )
  }

  const sorted = [...members].sort((a, b) => {
    const statusOrder = { over: 0, at: 1, under: 2, 'no-data': 3 }
    const statusA = getCapacityStatus(a.utilization, a.over_allocation)
    const statusB = getCapacityStatus(b.utilization, b.over_allocation)
    return statusOrder[statusA] - statusOrder[statusB]
  })

  return (
    <Table caption="Team capacity by person">
      <thead>
        <tr>
          <Th scope="col">Person</Th>
          <Th scope="col">Capacity</Th>
          <Th scope="col" className="text-right">
            Effective
          </Th>
          <Th scope="col" className="text-right">
            Allocated
          </Th>
          <Th scope="col" className="text-right">
            Remaining
          </Th>
          <Th scope="col" className="text-right">
            Utilization
          </Th>
          <Th scope="col">Status</Th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((member) => {
          const person = peopleLookup.get(member.person_id)
          const status = getCapacityStatus(
            member.utilization,
            member.over_allocation,
          )
          return (
            <tr key={member.person_id}>
              <Td>
                <Link
                  to={`/capacity/people/${member.person_id}`}
                  className="font-medium text-slate-100 underline-offset-2 hover:text-indigo-300 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
                >
                  {person?.display_name ?? 'Unknown person'}
                </Link>
                {person?.job_title ? (
                  <div className="text-xs text-slate-400">
                    {person.job_title}
                  </div>
                ) : null}
              </Td>
              <Td className="min-w-[120px]">
                <CapacityBar
                  effectiveCapacity={member.effective_capacity}
                  allocatedCapacity={member.allocated_hours}
                  remainingCapacity={member.remaining_capacity}
                  overAllocation={member.over_allocation}
                />
              </Td>
              <Td className="text-right tabular-nums">
                {formatHours(member.effective_capacity)}
              </Td>
              <Td className="text-right tabular-nums">
                {formatHours(member.allocated_hours)}
              </Td>
              <Td className="text-right tabular-nums">
                {formatHours(member.remaining_capacity)}
              </Td>
              <Td className="text-right tabular-nums">
                {formatUtilization(member.utilization)}
              </Td>
              <Td>
                <StatusBadge status={status} />
              </Td>
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}

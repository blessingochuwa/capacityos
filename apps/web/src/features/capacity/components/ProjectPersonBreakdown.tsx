import { Link } from 'react-router-dom'
import { Table, Td, Th } from '@/components/ui/Table'
import { EmptyState } from '@/components/ui/EmptyState'
import { toNumber } from '@/lib/decimal'
import type { Person } from '@/types/entities'
import type { ProjectPersonDemand } from '../types/capacity'
import { formatHours } from '../utils/presentation'

interface ProjectPersonBreakdownProps {
  byPerson: ProjectPersonDemand[]
  peopleLookup: Map<string, Person>
}

/** Who this project's demand is attributed to (spec §12: "affected people"). */
export function ProjectPersonBreakdown({
  byPerson,
  peopleLookup,
}: ProjectPersonBreakdownProps) {
  if (byPerson.length === 0) {
    return <EmptyState title="No allocations found for this period." />
  }

  const sorted = [...byPerson].sort(
    (a, b) => toNumber(b.allocated_hours) - toNumber(a.allocated_hours),
  )

  return (
    <Table caption="Project demand by person">
      <thead>
        <tr>
          <Th scope="col">Person</Th>
          <Th scope="col" className="text-right">
            Allocated
          </Th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((entry) => {
          const person = peopleLookup.get(entry.person_id)
          return (
            <tr key={entry.person_id}>
              <Td>
                <Link
                  to={`/capacity/people/${entry.person_id}`}
                  className="font-medium text-slate-100 underline-offset-2 hover:text-indigo-300 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
                >
                  {person?.display_name ?? 'Unknown person'}
                </Link>
              </Td>
              <Td className="text-right tabular-nums">
                {formatHours(entry.allocated_hours)}
              </Td>
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}

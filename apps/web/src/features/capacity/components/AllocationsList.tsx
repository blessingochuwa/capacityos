import { Link } from 'react-router-dom'
import { Table, Td, Th } from '@/components/ui/Table'
import { EmptyState } from '@/components/ui/EmptyState'
import type { Allocation, Project } from '@/types/entities'
import { formatHours } from '../utils/presentation'

interface AllocationsListProps {
  allocations: Allocation[]
  projectsLookup: Map<string, Project>
}

/** The allocations behind a person's "allocated capacity" number — lets the
 * user understand WHY it looks the way it does (spec §13/§14). */
export function AllocationsList({
  allocations,
  projectsLookup,
}: AllocationsListProps) {
  if (allocations.length === 0) {
    return <EmptyState title="No allocations found for this person." />
  }

  return (
    <Table caption="Allocations">
      <thead>
        <tr>
          <Th scope="col">Project</Th>
          <Th scope="col">Period</Th>
          <Th scope="col" className="text-right">
            Hours
          </Th>
          <Th scope="col">Notes</Th>
        </tr>
      </thead>
      <tbody>
        {allocations.map((allocation) => {
          const project = projectsLookup.get(allocation.project_id)
          return (
            <tr key={allocation.id}>
              <Td>
                {project ? (
                  <Link
                    to={`/capacity/projects/${project.id}`}
                    className="font-medium text-slate-100 underline-offset-2 hover:text-indigo-300 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
                  >
                    {project.name}
                  </Link>
                ) : (
                  'Unknown project'
                )}
              </Td>
              <Td>
                {allocation.start_date} – {allocation.end_date}
              </Td>
              <Td className="text-right tabular-nums">
                {formatHours(allocation.allocation_hours)}
              </Td>
              <Td className="text-slate-400">{allocation.notes ?? '—'}</Td>
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}

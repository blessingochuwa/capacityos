import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/Badge'
import { Table, Td, Th } from '@/components/ui/Table'
import {
  formatHours,
  formatUtilization,
} from '@/features/capacity/utils/presentation'
import type { PersonCapacityComparison } from '../types/scenario'

interface PeopleComparisonTableProps {
  people: PersonCapacityComparison[]
}

/** Per-person baseline → scenario, same shape as ComparisonTable but at
 * person granularity — answers "who specifically is affected, and how"
 * (prompt §16: "Baseline vs Scenario summary... display clear delta
 * indicators"). Over-allocated rows are marked, never colour-only
 * (CLAUDE.md §29). */
export function PeopleComparisonTable({ people }: PeopleComparisonTableProps) {
  return (
    <Table caption="Per-person baseline versus scenario capacity">
      <thead>
        <tr>
          <Th scope="col">Person</Th>
          <Th scope="col">Baseline utilization</Th>
          <Th scope="col">Scenario utilization</Th>
          <Th scope="col">Scenario over-allocation</Th>
        </tr>
      </thead>
      <tbody>
        {people.map((person) => (
          <tr key={person.person_id}>
            <Td>
              {person.is_hypothetical ? (
                <span className="text-slate-200">
                  {person.label} <Badge variant="info">Hypothetical</Badge>
                </span>
              ) : (
                <Link
                  to={`/capacity/people/${person.person_id}`}
                  className="font-medium text-indigo-300 hover:text-indigo-200"
                >
                  {person.label}
                </Link>
              )}
            </Td>
            <Td>{formatUtilization(person.baseline.utilization)}</Td>
            <Td>{formatUtilization(person.scenario.utilization)}</Td>
            <Td>
              {Number(person.scenario.over_allocation) > 0 ? (
                <Badge variant="danger">
                  {formatHours(person.scenario.over_allocation)} over
                  {person.newly_over_allocated ? ' (new)' : ''}
                </Badge>
              ) : (
                <span className="text-slate-400">None</span>
              )}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

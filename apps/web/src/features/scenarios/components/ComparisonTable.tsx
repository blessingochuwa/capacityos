import { Table, Td, Th } from '@/components/ui/Table'
import {
  formatHours,
  formatUtilization,
} from '@/features/capacity/utils/presentation'
import type { AggregateComparison } from '../types/scenario'
import {
  formatCountDelta,
  formatHoursDelta,
  formatUtilizationDelta,
} from '../utils/presentation'

interface ComparisonTableProps {
  aggregate: AggregateComparison
}

/** Baseline → Scenario → Change, one row per metric (prompt §19) — the
 * primary "what changed" surface, always three explicit columns rather
 * than a single merged number. */
export function ComparisonTable({ aggregate }: ComparisonTableProps) {
  return (
    <Table caption="Baseline versus scenario capacity comparison">
      <thead>
        <tr>
          <Th scope="col">Metric</Th>
          <Th scope="col">Baseline</Th>
          <Th scope="col">Scenario</Th>
          <Th scope="col">Change</Th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <Td>Utilization</Td>
          <Td>{formatUtilization(aggregate.utilization.baseline)}</Td>
          <Td>{formatUtilization(aggregate.utilization.scenario)}</Td>
          <Td>{formatUtilizationDelta(aggregate.utilization.delta)}</Td>
        </tr>
        <tr>
          <Td>Remaining capacity</Td>
          <Td>{formatHours(aggregate.remaining_capacity.baseline)}</Td>
          <Td>{formatHours(aggregate.remaining_capacity.scenario)}</Td>
          <Td>{formatHoursDelta(aggregate.remaining_capacity.delta)}</Td>
        </tr>
        <tr>
          <Td>Over-allocation</Td>
          <Td>{formatHours(aggregate.over_allocation.baseline)}</Td>
          <Td>{formatHours(aggregate.over_allocation.scenario)}</Td>
          <Td>{formatHoursDelta(aggregate.over_allocation.delta)}</Td>
        </tr>
        <tr>
          <Td>Over-allocated people</Td>
          <Td>{aggregate.over_allocated_people.baseline}</Td>
          <Td>{aggregate.over_allocated_people.scenario}</Td>
          <Td>{formatCountDelta(aggregate.over_allocated_people.delta)}</Td>
        </tr>
      </tbody>
    </Table>
  )
}

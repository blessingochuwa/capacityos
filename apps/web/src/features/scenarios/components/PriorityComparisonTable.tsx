import { Badge } from '@/components/ui/Badge'
import { Table, Td, Th } from '@/components/ui/Table'
import type { MoscowCategory } from '@/features/prioritization/types/prioritization'
import type { ScenarioPriorityProjectComparison } from '../types/scenarioPriority'

const MOSCOW_LABELS: Record<MoscowCategory, string> = {
  must: 'Must',
  should: 'Should',
  could: 'Could',
  wont: "Won't",
}

function statusFor(
  score: string | null,
  category: MoscowCategory | null,
  missingCriteria: string[],
) {
  if (category !== null) return <Badge variant="info">{MOSCOW_LABELS[category]}</Badge>
  if (missingCriteria.length > 0) {
    return <Badge variant="warning">Missing {missingCriteria.join(', ')}</Badge>
  }
  if (score === null) return <Badge variant="warning">No category set</Badge>
  return <Badge variant="success">Complete</Badge>
}

/** Baseline vs. scenario, per project — the primary "what would change"
 * surface for a scenario's hypothetical prioritization inputs (Phase 20).
 * A project with no override at all still appears here, unchanged, so
 * "nothing moved for this project" is a visible, positive fact, never an
 * absence. */
export function PriorityComparisonTable({ items }: { items: ScenarioPriorityProjectComparison[] }) {
  return (
    <Table caption="Baseline versus scenario prioritization comparison">
      <thead>
        <tr>
          <Th scope="col">Project</Th>
          <Th scope="col">Baseline rank</Th>
          <Th scope="col">Baseline score</Th>
          <Th scope="col">Baseline status</Th>
          <Th scope="col">Scenario rank</Th>
          <Th scope="col">Scenario score</Th>
          <Th scope="col">Scenario status</Th>
          <Th scope="col">Change</Th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.project_id}>
            <Td className="font-medium text-slate-200">
              {item.project_name}
              {item.has_override ? (
                <Badge variant="neutral">Hypothetical values</Badge>
              ) : null}
            </Td>
            <Td className="tabular-nums text-slate-400">{item.baseline_rank ?? '—'}</Td>
            <Td className="tabular-nums">{item.baseline_score ?? '—'}</Td>
            <Td>{statusFor(item.baseline_score, item.baseline_category, item.baseline_missing_criteria)}</Td>
            <Td className="tabular-nums text-slate-400">{item.scenario_rank ?? '—'}</Td>
            <Td className="tabular-nums">{item.scenario_score ?? '—'}</Td>
            <Td>{statusFor(item.scenario_score, item.scenario_category, item.scenario_missing_criteria)}</Td>
            <Td>
              {item.changed ? (
                <Badge variant="warning">Changed</Badge>
              ) : (
                <span className="text-slate-400">No change</span>
              )}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

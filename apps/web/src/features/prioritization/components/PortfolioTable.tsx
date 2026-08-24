import { Badge } from '@/components/ui/Badge'
import { Table, Td, Th } from '@/components/ui/Table'
import type { MoscowCategory, PortfolioRankingEntry } from '../types/prioritization'

interface PortfolioTableProps {
  items: PortfolioRankingEntry[]
  onSelectProject?: (projectId: string) => void
}

const MOSCOW_LABELS: Record<MoscowCategory, string> = {
  must: 'Must',
  should: 'Should',
  could: 'Could',
  wont: "Won't",
}

/** The Portfolio Priority Board (CLAUDE.md §38: "What happens if we accept
 * this work?" / "what should we work on first?"). A project with an
 * incomplete score (missing_criteria non-empty) is listed with no rank —
 * never silently sorted as if a missing input were zero (see
 * app/domain/prioritization.py's module docstring). A MoSCoW-framework
 * entry (Phase 18) never has a numeric score or rank at all — its
 * category is shown in the Status column instead, or "No category set"
 * when the project hasn't been assigned one yet (score === null and
 * missing_criteria is empty is MoSCoW's exact "not yet categorized"
 * signature, since every other framework type either produces a number
 * or lists what's missing). */
export function PortfolioTable({ items, onSelectProject }: PortfolioTableProps) {
  return (
    <Table caption="Portfolio priority ranking">
      <thead>
        <tr>
          <Th scope="col">Rank</Th>
          <Th scope="col">Project</Th>
          <Th scope="col">Score</Th>
          <Th scope="col">Status</Th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.project_id}>
            <Td className="tabular-nums text-slate-400">{item.rank ?? '—'}</Td>
            <Td>
              {onSelectProject ? (
                <button
                  type="button"
                  onClick={() => onSelectProject(item.project_id)}
                  className="text-left font-medium text-indigo-300 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
                >
                  {item.project_name}
                </button>
              ) : (
                item.project_name
              )}
            </Td>
            <Td className="tabular-nums">{item.score ?? '—'}</Td>
            <Td>
              {item.category !== null ? (
                <Badge variant="info">{MOSCOW_LABELS[item.category]}</Badge>
              ) : item.missing_criteria.length > 0 ? (
                <Badge variant="warning">
                  Missing {item.missing_criteria.join(', ')}
                </Badge>
              ) : item.score === null ? (
                <Badge variant="warning">No category set</Badge>
              ) : (
                <Badge variant="success">Complete</Badge>
              )}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

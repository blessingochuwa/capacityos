import { Badge } from '@/components/ui/Badge'
import { Table, Td, Th } from '@/components/ui/Table'
import type { PortfolioRankingEntry } from '../types/prioritization'

interface PortfolioTableProps {
  items: PortfolioRankingEntry[]
  onSelectProject?: (projectId: string) => void
}

/** The Portfolio Priority Board (CLAUDE.md §38: "What happens if we accept
 * this work?" / "what should we work on first?"). A project with an
 * incomplete score (missing_criteria non-empty) is listed with no rank —
 * never silently sorted as if a missing input were zero (see
 * app/domain/prioritization.py's module docstring). */
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
              {item.missing_criteria.length > 0 ? (
                <Badge variant="warning">
                  Missing {item.missing_criteria.join(', ')}
                </Badge>
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

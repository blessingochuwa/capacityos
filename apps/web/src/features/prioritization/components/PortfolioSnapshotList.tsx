import { Table, Td, Th } from '@/components/ui/Table'
import type { PortfolioSnapshot } from '../types/prioritization'

interface PortfolioSnapshotListProps {
  snapshots: PortfolioSnapshot[]
  selectedId: string | undefined
  onSelect: (id: string) => void
}

/** A history list of frozen rankings (CLAUDE.md §38: the trend/history
 * question the live Portfolio Priority Board can't answer on its own —
 * "what did this ranking look like before?"). Each row's rank/score is
 * exactly what was true AT CAPTURE TIME, never recomputed — see
 * app/models/portfolio_snapshot.py's docstring. Selecting a row shows its
 * frozen entries below via PortfolioTable, reused as-is since a snapshot
 * entry has the identical shape to a live ranking entry. */
export function PortfolioSnapshotList({
  snapshots,
  selectedId,
  onSelect,
}: PortfolioSnapshotListProps) {
  return (
    <Table caption="Portfolio snapshot history">
      <thead>
        <tr>
          <Th scope="col">Taken at</Th>
          <Th scope="col">Projects</Th>
          <Th scope="col">
            <span className="sr-only">View</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {snapshots.map((snapshot) => (
          <tr key={snapshot.id}>
            <Td className="font-medium text-slate-100">
              {new Date(snapshot.taken_at).toLocaleString()}
            </Td>
            <Td className="tabular-nums">{snapshot.entries.length}</Td>
            <Td>
              <button
                type="button"
                onClick={() => onSelect(snapshot.id)}
                aria-pressed={selectedId === snapshot.id}
                className="text-left font-medium text-indigo-300 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
              >
                {selectedId === snapshot.id ? 'Viewing' : 'View'}
              </button>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

import { Badge } from '@/components/ui/Badge'
import { Table, Td, Th } from '@/components/ui/Table'
import type { MoscowCategory, SnapshotComparisonItem } from '../types/prioritization'

const MOSCOW_LABELS: Record<MoscowCategory, string> = {
  must: 'Must',
  should: 'Should',
  could: 'Could',
  wont: "Won't",
}

const STATUS_BADGE: Record<
  SnapshotComparisonItem['status'],
  { label: string; variant: 'success' | 'warning' | 'neutral' | 'info' }
> = {
  entered: { label: 'Entered', variant: 'info' },
  left: { label: 'Left', variant: 'neutral' },
  changed: { label: 'Changed', variant: 'warning' },
  unchanged: { label: 'No change', variant: 'success' },
}

function rankCell(rank: number | null) {
  return <Td className="tabular-nums text-slate-400">{rank ?? '—'}</Td>
}

function scoreCell(score: string | null, category: MoscowCategory | null) {
  if (category !== null) return <Td>{MOSCOW_LABELS[category]}</Td>
  return <Td className="tabular-nums">{score ?? '—'}</Td>
}

/** Two immutable snapshots, diffed (Phase 22) — "what changed in this
 * portfolio's ranking between these two points in time?" Every value
 * shown is exactly what each snapshot already froze at capture time
 * (Phase 21) — nothing here is recalculated. A project entering or
 * leaving the ranked set is shown as a fact, not an error: `rank_from`/
 * `score_from` are blank for an entered project, `rank_to`/`score_to`
 * are blank for one that left. */
export function PortfolioSnapshotComparisonTable({ items }: { items: SnapshotComparisonItem[] }) {
  return (
    <Table caption="Snapshot comparison">
      <thead>
        <tr>
          <Th scope="col">Project</Th>
          <Th scope="col">Status</Th>
          <Th scope="col">Rank (from)</Th>
          <Th scope="col">Rank (to)</Th>
          <Th scope="col">Score/category (from)</Th>
          <Th scope="col">Score/category (to)</Th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => {
          const badge = STATUS_BADGE[item.status]
          return (
            <tr key={item.project_id}>
              <Td className="font-medium text-slate-200">{item.project_name}</Td>
              <Td>
                <Badge variant={badge.variant}>{badge.label}</Badge>
              </Td>
              {rankCell(item.rank_from)}
              {rankCell(item.rank_to)}
              {scoreCell(item.score_from, item.category_from)}
              {scoreCell(item.score_to, item.category_to)}
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}

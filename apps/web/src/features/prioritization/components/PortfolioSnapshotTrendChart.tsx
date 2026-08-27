import { useMemo, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { buildSnapshotTrend } from '../utils/snapshotTrend'
import type { PortfolioSnapshot } from '../types/prioritization'

const LINE_COLORS = ['#818cf8', '#34d399', '#38bdf8', '#fb7185', '#fbbf24', '#a78bfa']

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface TrendTooltipPayloadEntry {
  dataKey: string
  value: number | null
  color: string
  name: string
}

function TrendTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: TrendTooltipPayloadEntry[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null
  const present = payload.filter((entry) => entry.value !== null)
  if (present.length === 0) return null
  return (
    <div className="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 shadow-lg">
      <p className="mb-1 font-medium text-slate-100">{label ? formatTimestamp(label) : ''}</p>
      {present.map((entry) => (
        <p key={entry.dataKey} style={{ color: entry.color }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  )
}

/**
 * Phase 24 — "how has this project's priority score moved over time?"
 * (CLAUDE.md §38). Built entirely from GET /api/v1/prioritization/snapshots
 * data the parent already fetched — no new backend endpoint, no
 * recalculation: every plotted value is a frozen Phase 21 snapshot score,
 * exactly as captured (see utils/snapshotTrend.ts). A MoSCoW framework, or
 * any selection with no numeric score at all, renders an explanatory empty
 * state rather than a misleading blank chart. Chart + accessible table
 * pairing matches ProjectDemandTimeline's established precedent — colour
 * is never the only signal (CLAUDE.md §29): every line has a legend label,
 * a tooltip name, and a table column.
 */
export function PortfolioSnapshotTrendChart({ snapshots }: { snapshots: PortfolioSnapshot[] }) {
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  const sortedForPicker = useMemo(
    () =>
      [...snapshots].sort(
        (a, b) => new Date(b.taken_at).getTime() - new Date(a.taken_at).getTime(),
      ),
    [snapshots],
  )

  const selectedSnapshots = useMemo(
    () => snapshots.filter((s) => selectedIds.includes(s.id)),
    [snapshots, selectedIds],
  )

  const trend = useMemo(() => buildSnapshotTrend(selectedSnapshots), [selectedSnapshots])

  function toggle(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]))
  }

  return (
    <div className="space-y-4">
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-slate-200">
          Select snapshots to trend (2 or more)
        </legend>
        <div className="max-h-48 overflow-y-auto rounded-md border border-slate-800">
          <Table caption="Snapshots available to trend">
            <thead>
              <tr>
                <Th scope="col">
                  <span className="sr-only">Include</span>
                </Th>
                <Th scope="col">Taken at</Th>
                <Th scope="col">Projects</Th>
              </tr>
            </thead>
            <tbody>
              {sortedForPicker.map((snapshot) => (
                <tr key={snapshot.id}>
                  <Td>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(snapshot.id)}
                      onChange={() => toggle(snapshot.id)}
                      aria-label={`Include snapshot taken at ${formatTimestamp(snapshot.taken_at)}`}
                    />
                  </Td>
                  <Td className="font-medium text-slate-100">
                    {formatTimestamp(snapshot.taken_at)}
                  </Td>
                  <Td className="tabular-nums">{snapshot.entries.length}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </fieldset>

      {selectedIds.length < 2 ? (
        <EmptyState title="Select at least 2 snapshots above to see a trend." />
      ) : trend.projects.length === 0 ? (
        <EmptyState title="None of the selected snapshots have a numeric score to trend." />
      ) : (
        <div className="space-y-4">
          <div className="h-64 w-full" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend.rows} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis
                  dataKey="taken_at"
                  tickFormatter={formatTimestamp}
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                />
                <YAxis stroke="#64748b" fontSize={12} tickLine={false} width={48} />
                <Tooltip content={<TrendTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {trend.projects.map((project, index) => (
                  <Line
                    key={project.project_id}
                    dataKey={project.project_id}
                    name={project.project_name}
                    stroke={LINE_COLORS[index % LINE_COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <Table caption="Snapshot score trend">
            <thead>
              <tr>
                <Th scope="col">Taken at</Th>
                {trend.projects.map((project) => (
                  <Th key={project.project_id} scope="col">
                    {project.project_name}
                  </Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trend.rows.map((row) => (
                <tr key={row.snapshot_id}>
                  <Td className="font-medium text-slate-100">
                    {formatTimestamp(row.taken_at)}
                  </Td>
                  {trend.projects.map((project) => (
                    <Td key={project.project_id} className="tabular-nums">
                      {row[project.project_id] ?? '—'}
                    </Td>
                  ))}
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </div>
  )
}

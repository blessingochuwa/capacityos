import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { buildPriorityEffortScatter } from '../utils/priorityEffortScatter'
import type { PortfolioRankingEntry, PrioritizationFrameworkType } from '../types/prioritization'

const POINT_COLOR = '#818cf8'

interface ScatterTooltipPayloadEntry {
  payload: { project_name: string; effort: number; priority: number }
}

function ScatterTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: ScatterTooltipPayloadEntry[]
}) {
  if (!active || !payload || payload.length === 0) return null
  const point = payload[0].payload
  return (
    <div className="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 shadow-lg">
      <p className="mb-1 font-medium text-slate-100">{point.project_name}</p>
      <p>Priority (score): {point.priority}</p>
      <p>Effort: {point.effort}</p>
    </div>
  )
}

/**
 * Phase 27 — the PRD's §15 "Priority vs. Effort scatter" visualization:
 * each project scored under a RICE or WSJF framework, plotted by its
 * already-computed score (Y — the standard "value vs. effort"
 * prioritization-matrix convention CLAUDE.md §18 already assumes) against
 * its effort-like criterion (X). Built entirely from GET
 * .../prioritization/portfolio — no new backend endpoint. No quadrant
 * lines or "quick win" thresholds are drawn: no such boundary is defined
 * anywhere in this codebase, and inventing one would be exactly the false
 * precision CLAUDE.md §17/§29 warn against — this is a plain scatter of
 * already-computed facts, not a judgment. Chart + accessible table
 * pairing matches WsjfBreakdownChart's/ProjectDemandTimeline's
 * established precedent.
 */
export function PriorityEffortScatterChart({
  frameworkType,
  items,
}: {
  frameworkType: PrioritizationFrameworkType
  items: PortfolioRankingEntry[]
}) {
  const points = buildPriorityEffortScatter(frameworkType, items)

  if (points.length === 0) {
    return <EmptyState title="No projects have a complete score to plot yet." />
  }

  return (
    <div className="space-y-4">
      <div className="h-64 w-full" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              type="number"
              dataKey="effort"
              name="Effort"
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              label={{ value: 'Effort', position: 'insideBottom', offset: -4, fill: '#64748b' }}
            />
            <YAxis
              type="number"
              dataKey="priority"
              name="Priority"
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              width={48}
              label={{
                value: 'Priority (score)',
                angle: -90,
                position: 'insideLeft',
                fill: '#64748b',
              }}
            />
            <Tooltip
              content={<ScatterTooltip />}
              cursor={{ strokeDasharray: '3 3', stroke: '#475569' }}
            />
            <Scatter data={points} fill={POINT_COLOR} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <Table caption="Priority vs. effort">
        <thead>
          <tr>
            <Th scope="col">Project</Th>
            <Th scope="col">Priority (score)</Th>
            <Th scope="col">Effort</Th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.project_id}>
              <Td className="font-medium text-slate-100">{point.project_name}</Td>
              <Td className="tabular-nums">{point.priority}</Td>
              <Td className="tabular-nums">{point.effort}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  )
}

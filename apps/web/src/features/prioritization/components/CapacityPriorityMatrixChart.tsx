import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import type { Allocation } from '@/types/entities'
import type { PortfolioRankingEntry } from '../types/prioritization'
import {
  QUADRANT_DESCRIPTION,
  QUADRANT_LABEL,
  buildCapacityPriorityMatrix,
  type CapacityPriorityExclusionReason,
  type CapacityPriorityPoint,
} from '../utils/capacityPriorityMatrix'

const POINT_COLOR = '#818cf8'
const REFERENCE_LINE_COLOR = '#64748b'

const EXCLUSION_REASON_LABEL: Record<CapacityPriorityExclusionReason, string> = {
  no_priority_score: 'missing a priority score',
  no_capacity_data: 'missing capacity data (no recorded allocations)',
  no_priority_score_and_no_capacity_data: 'missing both a priority score and capacity data',
}

interface ScatterTooltipPayloadEntry {
  payload: CapacityPriorityPoint
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
      <p>Priority (score): {point.priority_score}</p>
      <p>Capacity (hours): {point.capacity_hours}</p>
      <p>Quadrant: {QUADRANT_LABEL[point.quadrant]}</p>
    </div>
  )
}

/**
 * Phase 42 — the PRD's §15 "Capacity vs. Priority matrix" visualization:
 * "which projects have high priority relative to the capacity required to
 * deliver them?" Each project scored under the currently selected
 * framework is plotted by its total allocated hours (X — every recorded
 * Allocation.allocation_hours for that project, summed verbatim) against
 * its already-computed priority score (Y — copied verbatim, never
 * recalculated). Built from GET /api/v1/prioritization/portfolio + GET
 * /api/v1/allocations, both already authorized and organization-scoped —
 * no new backend endpoint (mirrors the Phase 24/25/27/40 frontend-only
 * precedent). See utils/capacityPriorityMatrix.ts for the full data-
 * handling and median/quadrant rules.
 *
 * Reference lines are the MEDIAN capacity and MEDIAN priority across the
 * currently plotted projects only — never an invented business threshold
 * (CLAUDE.md §17/§29). Quadrants are purely descriptive positions, never a
 * recommendation ("quick win", "kill", "danger" labels are deliberately
 * never used). A project missing either value is never plotted at a
 * fabricated zero — it is excluded and disclosed below the chart.
 *
 * Chart (aria-hidden) + accessible table pairing matches every other
 * prioritization chart in this codebase (WsjfBreakdownChart,
 * PriorityEffortScatterChart, DependencyTimeline) — quadrant, reference
 * lines, and every plotted value are available as text, not only via
 * hover or position.
 */
export function CapacityPriorityMatrixChart({
  items,
  allocations,
}: {
  items: PortfolioRankingEntry[]
  allocations: Allocation[]
}) {
  const model = buildCapacityPriorityMatrix(items, allocations)
  const { points, excluded, medianCapacity, medianPriority } = model

  if (points.length === 0) {
    return (
      <EmptyState
        title="No projects have both a priority score and capacity data to plot yet."
        description="Projects without a priority score or capacity value are not plotted. Score a project above and record at least one allocation against it to see it here."
      />
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">
        Reference lines mark the median capacity ({medianCapacity} hours) and median
        priority ({medianPriority}) across the {points.length} plotted project
        {points.length === 1 ? '' : 's'}. A project exactly on a reference line is
        treated as being on the lower side of that axis.
      </p>

      <div className="h-72 w-full" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              type="number"
              dataKey="capacity_hours"
              name="Capacity"
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              label={{
                value: 'Capacity (hours)',
                position: 'insideBottom',
                offset: -4,
                fill: '#64748b',
              }}
            />
            <YAxis
              type="number"
              dataKey="priority_score"
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
            {medianCapacity !== null ? (
              <ReferenceLine
                x={medianCapacity}
                stroke={REFERENCE_LINE_COLOR}
                strokeDasharray="4 4"
                label={{ value: 'Median capacity', fill: REFERENCE_LINE_COLOR, fontSize: 11 }}
              />
            ) : null}
            {medianPriority !== null ? (
              <ReferenceLine
                y={medianPriority}
                stroke={REFERENCE_LINE_COLOR}
                strokeDasharray="4 4"
                label={{ value: 'Median priority', fill: REFERENCE_LINE_COLOR, fontSize: 11 }}
              />
            ) : null}
            <Tooltip
              content={<ScatterTooltip />}
              cursor={{ strokeDasharray: '3 3', stroke: '#475569' }}
            />
            <Scatter data={points} fill={POINT_COLOR} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <dl className="grid grid-cols-1 gap-2 text-xs text-slate-400 sm:grid-cols-2">
        {(Object.keys(QUADRANT_LABEL) as (keyof typeof QUADRANT_LABEL)[]).map((quadrant) => (
          <div key={quadrant} className="rounded-md border border-slate-800 px-3 py-2">
            <dt className="font-medium text-slate-200">{QUADRANT_LABEL[quadrant]}</dt>
            <dd>{QUADRANT_DESCRIPTION[quadrant]}</dd>
          </div>
        ))}
      </dl>

      <Table caption="Capacity vs. priority matrix">
        <thead>
          <tr>
            <Th scope="col">Project</Th>
            <Th scope="col">Capacity (hours)</Th>
            <Th scope="col">Priority (score)</Th>
            <Th scope="col">Quadrant</Th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.project_id}>
              <Td className="font-medium text-slate-100">{point.project_name}</Td>
              <Td className="tabular-nums">{point.capacity_hours}</Td>
              <Td className="tabular-nums">{point.priority_score}</Td>
              <Td>{QUADRANT_LABEL[point.quadrant]}</Td>
            </tr>
          ))}
        </tbody>
      </Table>

      {excluded.length > 0 ? (
        <p className="text-xs text-slate-500">
          {excluded.length} project{excluded.length === 1 ? '' : 's'} — {excluded
            .map((row) => `${row.project_name} (${EXCLUSION_REASON_LABEL[row.reason]})`)
            .join(', ')}{' '}
          — {excluded.length === 1 ? 'is' : 'are'} not plotted because a priority score or
          capacity value is not yet available.
        </p>
      ) : null}
    </div>
  )
}

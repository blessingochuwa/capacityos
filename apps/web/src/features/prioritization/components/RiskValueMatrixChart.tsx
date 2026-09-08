import { useMemo } from 'react'
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
import { LoadingState } from '@/components/ui/Skeleton'
import { Table, Td, Th } from '@/components/ui/Table'
import type { PortfolioRankingEntry } from '../types/prioritization'
import { useRisksForProjects } from '../hooks/useRisksForProjects'
import {
  QUADRANT_DESCRIPTION,
  QUADRANT_LABEL,
  buildRiskValueMatrix,
  countOpenHighExposureRisks,
  type RiskValueExclusionReason,
  type RiskValuePoint,
} from '../utils/riskValueMatrix'

const POINT_COLOR = '#f472b6'
const REFERENCE_LINE_COLOR = '#64748b'

const EXCLUSION_REASON_LABEL: Record<RiskValueExclusionReason, string> = {
  no_priority_score: 'missing a priority score',
  risk_data_unavailable: 'risk data could not be loaded',
  no_priority_score_and_risk_data_unavailable:
    'missing a priority score and risk data could not be loaded',
}

interface ScatterTooltipPayloadEntry {
  payload: RiskValuePoint
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
      <p>Value (score): {point.value_score}</p>
      <p>Risk (open high-exposure): {point.risk_count}</p>
      <p>Quadrant: {QUADRANT_LABEL[point.quadrant]}</p>
    </div>
  )
}

/**
 * Phase 45 — the PRD's §15 "Risk vs. Value quadrant" visualization:
 * "which projects carry the most open risk relative to how valuable they
 * are?" Each project scored under the currently selected framework is
 * plotted by its count of open, high-exposure Risk records (X — see
 * utils/riskValueMatrix.ts::countOpenHighExposureRisks, reusing the exact
 * condition the existing `risk_high_exposure` Insights signal already
 * uses) against its already-computed priority score (Y — the same Value
 * definition Phase 42's Capacity-vs-Priority matrix already plots,
 * copied verbatim, never recalculated).
 *
 * Both definitions were explicit product decisions confirmed by the user
 * for this phase (Value = existing priority score; Risk = count of open
 * high-exposure risks) — see docs/adr/0045-risk-value-quadrant.md. Every
 * other prioritization visualization convention in this codebase already
 * established still applies: median reference lines (never an invented
 * threshold), purely descriptive quadrant labels (never a recommendation
 * — CLAUDE.md §17/§29), a project missing either value excluded and
 * disclosed rather than plotted at a fabricated zero.
 *
 * Risk data has no bulk endpoint (ADR 0013 — no org-wide risk register),
 * so this component fetches each plotted project's risks itself via
 * useRisksForProjects (one GET /projects/{id}/risks per project, in
 * parallel, reusing the existing per-project route and query key
 * features/risks/ already uses).
 */
export function RiskValueMatrixChart({ items }: { items: PortfolioRankingEntry[] }) {
  const projectIds = useMemo(() => items.map((item) => item.project_id), [items])
  const riskQueries = useRisksForProjects(projectIds)

  const isPending = riskQueries.some((query) => query.isPending)

  if (isPending) {
    return <LoadingState label="Loading risk data…" />
  }

  const riskCountsByProject = new Map<string, number>()
  projectIds.forEach((projectId, index) => {
    const result = riskQueries[index]
    if (result.isSuccess) {
      riskCountsByProject.set(projectId, countOpenHighExposureRisks(result.data ?? []))
    }
  })

  const model = buildRiskValueMatrix(items, riskCountsByProject)
  const { points, excluded, medianRisk, medianValue } = model

  if (points.length === 0) {
    return (
      <EmptyState
        title="No projects have both a priority score and available risk data to plot yet."
        description="Projects without a priority score, or whose risk data could not be loaded, are not plotted. Score a project above and record its risks on the Risks page to see it here."
      />
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">
        Reference lines mark the median risk ({medianRisk} open high-exposure risk
        {medianRisk === 1 ? '' : 's'}) and median value ({medianValue}) across the{' '}
        {points.length} plotted project{points.length === 1 ? '' : 's'}. A project exactly on
        a reference line is treated as being on the lower side of that axis.
      </p>

      <div className="h-72 w-full" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              type="number"
              dataKey="risk_count"
              name="Risk"
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              allowDecimals={false}
              label={{
                value: 'Risk (open high-exposure count)',
                position: 'insideBottom',
                offset: -4,
                fill: '#64748b',
              }}
            />
            <YAxis
              type="number"
              dataKey="value_score"
              name="Value"
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              width={48}
              label={{
                value: 'Value (score)',
                angle: -90,
                position: 'insideLeft',
                fill: '#64748b',
              }}
            />
            {medianRisk !== null ? (
              <ReferenceLine
                x={medianRisk}
                stroke={REFERENCE_LINE_COLOR}
                strokeDasharray="4 4"
                label={{ value: 'Median risk', fill: REFERENCE_LINE_COLOR, fontSize: 11 }}
              />
            ) : null}
            {medianValue !== null ? (
              <ReferenceLine
                y={medianValue}
                stroke={REFERENCE_LINE_COLOR}
                strokeDasharray="4 4"
                label={{ value: 'Median value', fill: REFERENCE_LINE_COLOR, fontSize: 11 }}
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

      <Table caption="Risk vs. value matrix">
        <thead>
          <tr>
            <Th scope="col">Project</Th>
            <Th scope="col">Risk (open high-exposure)</Th>
            <Th scope="col">Value (score)</Th>
            <Th scope="col">Quadrant</Th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.project_id}>
              <Td className="font-medium text-slate-100">{point.project_name}</Td>
              <Td className="tabular-nums">{point.risk_count}</Td>
              <Td className="tabular-nums">{point.value_score}</Td>
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
          risk data is not yet available.
        </p>
      ) : null}
    </div>
  )
}

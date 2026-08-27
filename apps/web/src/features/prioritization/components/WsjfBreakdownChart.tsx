import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { buildWsjfBreakdown } from '../utils/wsjfBreakdown'
import type { PortfolioRankingEntry } from '../types/prioritization'

const COST_OF_DELAY_COLORS = {
  business_value: '#818cf8',
  time_criticality: '#34d399',
  risk_reduction_opportunity_enablement: '#38bdf8',
}
const JOB_SIZE_COLOR = '#fbbf24'

const CRITERION_LABELS: Record<string, string> = {
  business_value: 'Business value',
  time_criticality: 'Time criticality',
  risk_reduction_opportunity_enablement: 'Risk reduction / opportunity enablement',
  job_size: 'Job size',
}

/**
 * Phase 25 — the PRD's §15 "WSJF breakdown (stacked bar of the four
 * inputs)" visualization, built entirely from GET
 * .../prioritization/portfolio (unchanged since Phase 17) — no new
 * backend endpoint. Business value/time criticality/risk reduction are
 * stacked together (their sum IS a meaningful number — SAFe's own "Cost
 * of Delay"), but Job Size is rendered as its own adjacent bar rather
 * than folded into the same stack: it is WSJF's *divisor*, not an
 * additive component, so stacking it with the other three would produce
 * a combined bar height that is not the WSJF score, not Cost of Delay,
 * and not any other meaningful number — exactly the kind of misleading
 * total CLAUDE.md §29/§17 warn against. Chart + accessible table pairing
 * matches ProjectDemandTimeline's/PortfolioSnapshotTrendChart's
 * established precedent.
 */
export function WsjfBreakdownChart({ items }: { items: PortfolioRankingEntry[] }) {
  const rows = buildWsjfBreakdown(items)

  if (rows.length === 0) {
    return (
      <EmptyState title="No projects have a complete WSJF score yet." />
    )
  }

  return (
    <div className="space-y-4">
      <div className="h-64 w-full" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis
              dataKey="project_name"
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              interval={0}
              angle={-15}
              textAnchor="end"
              height={50}
            />
            <YAxis stroke="#64748b" fontSize={12} tickLine={false} width={40} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                fontSize: 12,
              }}
              labelStyle={{ color: '#f1f5f9' }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar
              dataKey="business_value"
              name={CRITERION_LABELS.business_value}
              stackId="cost_of_delay"
              fill={COST_OF_DELAY_COLORS.business_value}
            />
            <Bar
              dataKey="time_criticality"
              name={CRITERION_LABELS.time_criticality}
              stackId="cost_of_delay"
              fill={COST_OF_DELAY_COLORS.time_criticality}
            />
            <Bar
              dataKey="risk_reduction_opportunity_enablement"
              name={CRITERION_LABELS.risk_reduction_opportunity_enablement}
              stackId="cost_of_delay"
              fill={COST_OF_DELAY_COLORS.risk_reduction_opportunity_enablement}
              radius={[3, 3, 0, 0]}
            />
            <Bar
              dataKey="job_size"
              name={CRITERION_LABELS.job_size}
              fill={JOB_SIZE_COLOR}
              radius={[3, 3, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <Table caption="WSJF criterion breakdown">
        <thead>
          <tr>
            <Th scope="col">Project</Th>
            <Th scope="col">Business value</Th>
            <Th scope="col">Time criticality</Th>
            <Th scope="col">Risk reduction / opportunity enablement</Th>
            <Th scope="col">Job size</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.project_id}>
              <Td className="font-medium text-slate-100">{row.project_name}</Td>
              <Td className="tabular-nums">{row.business_value}</Td>
              <Td className="tabular-nums">{row.time_criticality}</Td>
              <Td className="tabular-nums">{row.risk_reduction_opportunity_enablement}</Td>
              <Td className="tabular-nums">{row.job_size}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  )
}

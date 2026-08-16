import { MetricTile } from '@/components/ui/MetricTile'
import type { InsightsSummary } from '../types/insights'

/** "Where should I look?" (CLAUDE.md §38/§20) — a concise health readout,
 * not a dump of every number the summary carries. */
export function PlanningHealthSummary({
  summary,
}: {
  summary: InsightsSummary
}) {
  const { signal_counts, projects_under_pressure, scenario_new_risk_count } =
    summary
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <MetricTile
        label="Critical signals"
        value={signal_counts.critical}
        tone={signal_counts.critical > 0 ? 'danger' : 'default'}
      />
      <MetricTile
        label="Warnings"
        value={signal_counts.warning}
        tone={signal_counts.warning > 0 ? 'danger' : 'default'}
      />
      <MetricTile
        label="Projects under pressure"
        value={projects_under_pressure.length}
      />
      <MetricTile
        label="New scenario risks"
        value={summary.scenario_id !== null ? scenario_new_risk_count : '—'}
      />
    </div>
  )
}

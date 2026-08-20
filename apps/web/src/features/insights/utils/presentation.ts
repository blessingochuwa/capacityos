/** Pure string-templating/sorting helpers only — every number and every
 * classification (severity, is_new, trend) is already computed server-side
 * (app/services/insight_service.py). Nothing here recomputes a signal. */

import type {
  Severity,
  Signal,
  SignalType,
  UtilizationPoint,
} from '../types/insights'

/** A stable, derived key for a computed (not stored) signal — signals have
 * no id of their own, so entity+type is the natural composite identity
 * (classify_capacity_signal's mutual exclusivity means an entity never
 * carries two signals of the same type for the same period). */
export function signalKey(signal: Signal): string {
  return `${signal.type}-${signal.entity_type}-${signal.entity_id}`
}

export const SIGNAL_TYPE_LABEL: Record<SignalType, string> = {
  over_allocation: 'Over-allocated',
  zero_remaining_capacity: 'No remaining capacity',
  low_capacity: 'Low capacity',
  concentration_risk: 'Concentration risk',
  capacity_imbalance: 'Capacity imbalance',
  project_capacity_pressure: 'Project capacity pressure',
  scenario_new_risk: 'New scenario risk',
  scenario_existing_risk: 'Existing scenario risk',
  skill_gap: 'Skill gap',
  single_skill_holder: 'Single point of failure',
  skill_concentration: 'Skill concentration',
  risk_high_exposure: 'High-exposure risk',
  risk_review_overdue: 'Risk review overdue',
}

const SEVERITY_RANK: Record<Severity, number> = {
  critical: 0,
  warning: 1,
  info: 2,
}
const TYPE_RANK: Record<SignalType, number> = {
  over_allocation: 0,
  scenario_new_risk: 1,
  scenario_existing_risk: 1,
  risk_high_exposure: 1,
  low_capacity: 2,
  project_capacity_pressure: 2,
  skill_gap: 2,
  single_skill_holder: 2,
  risk_review_overdue: 2,
  zero_remaining_capacity: 3,
  capacity_imbalance: 4,
  concentration_risk: 5,
  skill_concentration: 5,
}

/** Mirrors InsightService._prioritize's sort key exactly
 * (apps/api/app/services/insight_service.py) — severity dominates, is_new/
 * type/label/id are tiebreakers within a severity tier only. The backend
 * already returns signals in this order; this is a defensive fallback for
 * merging multiple signal lists (e.g. team + project + scenario signals on
 * one page) or rendering fixtures that were constructed out of order, not a
 * re-derivation of priority itself. */
export function sortSignals(signals: Signal[]): Signal[] {
  return [...signals].sort((a, b) => {
    const severityDiff = SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]
    if (severityDiff !== 0) return severityDiff
    const isNewDiff = (a.is_new ? 0 : 1) - (b.is_new ? 0 : 1)
    if (isNewDiff !== 0) return isNewDiff
    const typeDiff = TYPE_RANK[a.type] - TYPE_RANK[b.type]
    if (typeDiff !== 0) return typeDiff
    const labelDiff = a.entity_label.localeCompare(b.entity_label)
    if (labelDiff !== 0) return labelDiff
    return a.entity_id.localeCompare(b.entity_id)
  })
}

/** Display slices of an already-sorted distribution — not a second invented
 * cutoff (see InsightsSummaryRead.utilization_distribution's own docstring:
 * "highest/lowest-N is a frontend array-slice concern"). */
export function topUtilization(
  points: UtilizationPoint[],
  n: number,
): UtilizationPoint[] {
  return points.slice(0, n)
}

export function bottomUtilization(
  points: UtilizationPoint[],
  n: number,
): UtilizationPoint[] {
  return points.slice(-n).reverse()
}

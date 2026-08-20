/**
 * Mirrors apps/api/app/schemas/insights.py verbatim. Never compute
 * severity, thresholds, or capacity numbers in TypeScript here — unlike
 * features/capacity's getCapacityStatus (which derives status itself),
 * Phase 5 signals arrive pre-classified and pre-explained from the API. See
 * docs/adr/0005-phase-5-operational-insights.md.
 */

import type {
  AggregateCapacity,
  AggregateComparison,
} from '@/features/scenarios/types/scenario'

export type SignalType =
  | 'over_allocation'
  | 'zero_remaining_capacity'
  | 'low_capacity'
  | 'concentration_risk'
  | 'capacity_imbalance'
  | 'project_capacity_pressure'
  | 'scenario_new_risk'
  | 'scenario_existing_risk'
  | 'skill_gap'
  | 'single_skill_holder'
  | 'skill_concentration'
  | 'risk_high_exposure'
  | 'risk_review_overdue'

export type Severity = 'critical' | 'warning' | 'info'
export type EntityType = 'person' | 'team' | 'project'
export type SignalTrend = 'worsened' | 'improved' | 'unchanged'

export interface Signal {
  type: SignalType
  severity: Severity
  entity_type: EntityType
  entity_id: string
  entity_label: string
  start_date: string
  end_date: string
  /** A complete, human-readable sentence — render verbatim, never
   * reconstruct it from the numeric fields below. */
  explanation: string

  effective_capacity: string | null
  allocated_hours: string | null
  remaining_capacity: string | null
  excess_hours: string | null
  utilization: string | null
  threshold_hours_per_day: string | null

  concentration_ratio: string | null
  concentration_person_ids: string[] | null
  concentration_person_labels: string[] | null

  min_utilization: string | null
  min_utilization_person_id: string | null
  min_utilization_person_label: string | null
  max_utilization: string | null
  max_utilization_person_id: string | null
  max_utilization_person_label: string | null

  affected_person_ids: string[]
  contributing_allocation_ids: string[]

  scenario_id: string | null
  is_new: boolean | null
  trend: SignalTrend | null
  baseline_value: string | null
  scenario_value: string | null

  skill_id: string | null
  skill_label: string | null

  skill_required_hours: string | null
  skill_qualified_available_hours: string | null
  skill_coverage_ratio: string | null
  skill_gap_hours: string | null

  skill_holder_ids: string[] | null
  skill_holder_labels: string[] | null
  skill_holder_ratio: string | null

  risk_id: string | null
  risk_description: string | null
  risk_probability: 'low' | 'medium' | 'high' | null
  risk_impact: 'low' | 'medium' | 'high' | null
  risk_exposure: 'low' | 'medium' | 'high' | null
  risk_status: 'open' | 'mitigating' | 'monitoring' | 'closed' | null
  risk_owner_person_id: string | null
  risk_owner_label: string | null
  risk_review_date: string | null
}

export interface SeverityCounts {
  critical: number
  warning: number
  info: number
}

export interface UtilizationPoint {
  person_id: string
  label: string
  utilization: string | null
}

export interface ConcentrationArea {
  project_id: string
  project_label: string
  ratio: string
  top_contributor_ids: string[]
  top_contributor_labels: string[]
}

export interface ProjectPressure {
  project_id: string
  project_label: string
  severity: Severity
  demand_hours: string
  available_capacity: string
  remaining_capacity: string
}

export interface InsightsSummary {
  team_id: string
  team_label: string
  start_date: string
  end_date: string
  capacity: AggregateCapacity
  signal_counts: SeverityCounts
  utilization_distribution: UtilizationPoint[]
  concentration_areas: ConcentrationArea[]
  projects_under_pressure: ProjectPressure[]
  scenario_id: string | null
  scenario_delta: AggregateComparison | null
  scenario_new_risk_count: number
  scenario_existing_risk_count: number
}

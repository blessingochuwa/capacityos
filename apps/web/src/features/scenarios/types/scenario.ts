/**
 * Mirrors apps/api/app/schemas/scenario.py verbatim — same convention as
 * features/capacity/types/capacity.ts. Never compute capacity numbers in
 * TypeScript here; these ARE the backend's numbers, and comparisons/deltas
 * are already computed server-side (see docs/adr/0004-phase-4-scenario-planning.md).
 */

import type { ProjectDemand } from '@/features/capacity/types/capacity'

export type ScenarioStatus = 'draft' | 'active' | 'archived'

export interface Scenario {
  id: string
  name: string
  description: string | null
  status: ScenarioStatus
  baseline_start_date: string
  baseline_end_date: string
  created_by: string | null
  created_at: string
  updated_at: string
}

export type ScenarioOperationType =
  | 'add_allocation'
  | 'adjust_allocation'
  | 'remove_allocation'
  | 'move_allocation'
  | 'shift_project'
  | 'availability_override'
  | 'availability_clear'
  | 'add_hypothetical_resource'

export interface AddAllocationPayload {
  operation_type: 'add_allocation'
  person_id: string
  project_id: string
  hours: string
  start_date: string
  end_date: string
}

export interface AdjustAllocationPayload {
  operation_type: 'adjust_allocation'
  allocation_id: string
  hours: string | null
  start_date: string | null
  end_date: string | null
}

export interface RemoveAllocationPayload {
  operation_type: 'remove_allocation'
  allocation_id: string
}

export interface MoveAllocationPayload {
  operation_type: 'move_allocation'
  allocation_id: string
  to_person_id: string
  hours: string | null
}

export interface ShiftProjectPayload {
  operation_type: 'shift_project'
  project_id: string
  day_offset: number
}

export interface AvailabilityOverridePayload {
  operation_type: 'availability_override'
  person_id: string
  start_date: string
  end_date: string
  hours: string | null
}

export interface AvailabilityClearPayload {
  operation_type: 'availability_clear'
  person_id: string
  start_date: string
  end_date: string
}

export interface AddHypotheticalResourcePayload {
  operation_type: 'add_hypothetical_resource'
  label: string
  hours_per_week: string
  start_date: string
  end_date: string
}

export type ScenarioOperationPayload =
  | AddAllocationPayload
  | AdjustAllocationPayload
  | RemoveAllocationPayload
  | MoveAllocationPayload
  | ShiftProjectPayload
  | AvailabilityOverridePayload
  | AvailabilityClearPayload
  | AddHypotheticalResourcePayload

export interface ScenarioOperation {
  id: string
  scenario_id: string
  operation_type: ScenarioOperationType
  sequence: number
  payload: ScenarioOperationPayload
  created_at: string
  updated_at: string
}

export interface AggregateCapacity {
  start_date: string
  end_date: string
  gross_capacity: string
  unavailable_hours: string
  effective_capacity: string
  allocated_hours: string
  remaining_capacity: string
  utilization: string | null
  over_allocation: string
}

export interface PersonCapacitySnapshot {
  person_id: string
  label: string
  /** true for a hypothetical resource introduced by an
   * add_hypothetical_resource operation — no Person row exists for it. */
  is_hypothetical: boolean
  start_date: string
  end_date: string
  gross_capacity: string
  unavailable_hours: string
  effective_capacity: string
  allocated_hours: string
  remaining_capacity: string
  utilization: string | null
  over_allocation: string
}

export interface ScenarioSnapshot {
  aggregate: AggregateCapacity
  people: PersonCapacitySnapshot[]
  projects: ProjectDemand[]
}

export interface ScenarioResults {
  scenario: Scenario
  baseline: ScenarioSnapshot
  scenario_state: ScenarioSnapshot
}

export interface MetricDelta<T> {
  baseline: T
  scenario: T
  delta: T
}

export interface AggregateComparison {
  baseline: AggregateCapacity
  scenario: AggregateCapacity
  utilization: MetricDelta<string | null>
  remaining_capacity: MetricDelta<string>
  over_allocation: MetricDelta<string>
  over_allocated_people: MetricDelta<number>
}

export interface PersonCapacityComparison {
  person_id: string
  label: string
  is_hypothetical: boolean
  baseline: PersonCapacitySnapshot
  scenario: PersonCapacitySnapshot
  utilization: MetricDelta<string | null>
  remaining_capacity: MetricDelta<string>
  over_allocation: MetricDelta<string>
  /** baseline over_allocation was 0 and scenario over_allocation is > 0. */
  newly_over_allocated: boolean
}

export interface ProjectDemandComparison {
  project_id: string
  baseline: ProjectDemand
  scenario: ProjectDemand
  allocated_hours: MetricDelta<string>
}

export type RiskType = 'over_allocation' | 'zero_remaining_capacity'

export interface Risk {
  type: RiskType
  person_id: string
  label: string
  is_new: boolean
  baseline_value: string
  scenario_value: string
}

export interface Impact {
  affected_people: string[]
  affected_projects: string[]
  affected_teams: string[]
  affected_start_date: string | null
  affected_end_date: string | null
}

export interface ScenarioComparison {
  scenario: Scenario
  aggregate: AggregateComparison
  people: PersonCapacityComparison[]
  projects: ProjectDemandComparison[]
  risks: Risk[]
  impact: Impact
}

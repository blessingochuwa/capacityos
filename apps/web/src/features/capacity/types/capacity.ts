/**
 * Mirrors apps/api/app/schemas/capacity.py verbatim. This is the ONLY
 * source of capacity numbers in the frontend — see docs/adr/0003 and
 * CLAUDE.md §4/§10. Never compute effective/remaining/utilization/
 * over-allocation in TypeScript; only format/derive-a-status-label from
 * what these types already carry (see ../utils/presentation.ts).
 */

export interface DailyCapacity {
  date: string
  scheduled_hours: string
  unavailable_hours: string
  effective_capacity: string
  allocated_hours: string
  remaining_capacity: string
  /** null (not "0") when effective_capacity is 0 for this day — see
   * docs/domain-concepts.md#capacity-engine-phase-2. */
  utilization: string | null
  over_allocation: string
}

export interface PersonCapacity {
  person_id: string
  start_date: string
  end_date: string
  gross_capacity: string
  unavailable_hours: string
  effective_capacity: string
  allocated_hours: string
  remaining_capacity: string
  utilization: string | null
  over_allocation: string
  daily_breakdown: DailyCapacity[]
}

export interface TeamCapacity {
  team_id: string
  start_date: string
  end_date: string
  gross_capacity: string
  unavailable_hours: string
  effective_capacity: string
  allocated_hours: string
  remaining_capacity: string
  /** Weighted: sum(allocated) / sum(effective) across members — never an
   * average of member utilization percentages. See ADR 0003 decision on
   * team weighting. */
  utilization: string | null
  over_allocation: string
  members: PersonCapacity[]
}

export interface ProjectDailyDemand {
  date: string
  allocated_hours: string
}

export interface ProjectPersonDemand {
  person_id: string
  allocated_hours: string
}

export interface ProjectDemand {
  project_id: string
  start_date: string
  end_date: string
  allocated_hours: string
  allocated_people: number
  daily_breakdown: ProjectDailyDemand[]
  by_person: ProjectPersonDemand[]
}

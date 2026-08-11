/**
 * Hand-written TypeScript types mirroring apps/api's Pydantic Read schemas
 * verbatim (field names, nullability, and shape). Not generated — see
 * packages/contracts/README.md for why (revisit once the frontend surface
 * is large enough to justify OpenAPI codegen).
 *
 * Decimal-valued fields (hours, allocation_hours, ...) are typed `string`
 * because Pydantic serializes Decimal to a JSON string, never a float —
 * see apps/api/tests/api/test_allocations.py. Never `Number()` these except
 * at the single display boundary in src/lib/decimal.ts.
 */

export type EmploymentStatus = 'active' | 'inactive'
export type ProjectStatus = 'planned' | 'active' | 'completed' | 'cancelled'
export type AllocationUnit = 'total_hours'
export type AvailabilityType =
  | 'annual_leave'
  | 'sick_leave'
  | 'public_holiday'
  | 'training'
  | 'company_event'
  | 'parental_leave'
  | 'personal_leave'
  | 'reduced_availability'
  | 'other'

/** List-response envelope — apps/api/app/schemas/common.py::Page[T]. */
export interface Page<T> {
  items: T[]
  total: number
}

export interface Person {
  id: string
  first_name: string
  last_name: string
  display_name: string
  email: string
  job_title: string | null
  timezone: string
  employment_status: EmploymentStatus
  created_at: string
  updated_at: string
}

export interface Team {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface TeamMembership {
  id: string
  person_id: string
  team_id: string
  created_at: string
}

export interface Project {
  id: string
  name: string
  description: string | null
  status: ProjectStatus
  start_date: string | null
  end_date: string | null
  created_at: string
  updated_at: string
}

export interface Allocation {
  id: string
  person_id: string
  project_id: string
  start_date: string
  end_date: string
  allocation_hours: string
  allocation_unit: AllocationUnit
  notes: string | null
  created_at: string
  updated_at: string
}

export interface AvailabilityException {
  id: string
  person_id: string
  start_date: string
  end_date: string
  availability_type: AvailabilityType
  /** null = fully unavailable for the whole period; a value = hours
   * available PER DAY during the period. See docs/domain-concepts.md. */
  hours: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

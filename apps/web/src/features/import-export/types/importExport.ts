/**
 * Mirrors apps/api/app/schemas/import_export.py and
 * apps/api/app/domain/import_export_parsing.py verbatim. Never compute
 * validation/upsert classification in TypeScript — every row here arrives
 * pre-classified from the API, exactly like Phase 5 signals. See
 * docs/adr/0006-phase-6-import-export.md.
 */

export type ImportEntityType =
  | 'person'
  | 'team'
  | 'team_membership'
  | 'project'
  | 'allocation'
  | 'working_schedule'
  | 'availability_exception'
  | 'skill'
  | 'person_skill'
  | 'project_skill_requirement'
  | 'risk'
  | 'stakeholder'
  | 'project_priority_score'
  | 'project_dependency'

export type ImportMode = 'upsert' | 'create_only' | 'update_only'

export type ExportFormat = 'csv' | 'json'

export type ImportRowStatus =
  | 'valid_create'
  | 'valid_update'
  | 'valid_unchanged'
  | 'invalid'

export type ImportErrorCode =
  | 'file_unreadable'
  | 'unsupported_format'
  | 'file_too_large'
  | 'row_limit_exceeded'
  | 'duplicate_header'
  | 'missing_required_column'
  | 'field_required'
  | 'field_type_invalid'
  | 'field_constraint_violated'
  | 'invalid_reference'
  | 'domain_rule_violated'
  | 'duplicate_in_file'
  | 'conflict'
  | 'no_match_for_update_only'

export interface ImportFieldError {
  /** null for a row-level error not specific to one column. */
  field: string | null
  code: ImportErrorCode
  message: string
}

export interface ImportRowResult {
  /** 1-based, header row excluded. */
  row_number: number
  status: ImportRowStatus
  /** The identity used to match this row, e.g. "email=jane@x.com". null
   * when the entity has no natural key and the row would always create. */
  identity: string | null
  matched_id: string | null
  errors: ImportFieldError[]
}

export interface ImportValidationReport {
  entity_type: ImportEntityType
  mode: ImportMode
  /** A whole-file (Level 1) problem — parsing never reached individual
   * rows. When set, rows is empty and ready_to_apply is false. */
  file_error: ImportFieldError | null
  total_rows: number
  valid_create_count: number
  valid_update_count: number
  valid_unchanged_count: number
  invalid_count: number
  ready_to_apply: boolean
  rows: ImportRowResult[]
}

export interface ImportApplyResult {
  entity_type: ImportEntityType
  mode: ImportMode
  file_error: ImportFieldError | null
  /** false whenever anything failed — nothing was written
   * (all-or-nothing). */
  applied: boolean
  total_rows: number
  created_count: number
  updated_count: number
  unchanged_count: number
  invalid_count: number
  rows: ImportRowResult[]
}

export const IMPORT_ENTITY_TYPES: {
  value: ImportEntityType
  label: string
}[] = [
  { value: 'person', label: 'People' },
  { value: 'team', label: 'Teams' },
  { value: 'team_membership', label: 'Team memberships' },
  { value: 'project', label: 'Projects' },
  { value: 'allocation', label: 'Allocations' },
  { value: 'working_schedule', label: 'Working schedules' },
  { value: 'availability_exception', label: 'Availability exceptions' },
  { value: 'skill', label: 'Skills' },
  { value: 'person_skill', label: 'Person skills' },
  { value: 'project_skill_requirement', label: 'Project skill requirements' },
  { value: 'risk', label: 'Risks' },
  { value: 'stakeholder', label: 'Stakeholders' },
  { value: 'project_priority_score', label: 'Project priority scores' },
  { value: 'project_dependency', label: 'Project dependencies' },
]

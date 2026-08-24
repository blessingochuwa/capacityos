/**
 * Mirrors apps/api/app/schemas/scenario_priority.py verbatim (Phase 20 —
 * see docs/adr/0020-scenario-priority-comparison.md). A ScenarioPriorityOverride
 * never mutates the real, persisted ProjectPriorityScore — it's read
 * alongside it, at comparison time, and never written back.
 */

import type { MoscowCategory, PrioritizationFrameworkType } from '@/features/prioritization/types/prioritization'

export interface ScenarioPriorityOverride {
  id: string
  scenario_id: string
  project_id: string
  project_name: string
  framework_id: string
  framework_name: string
  framework_type: PrioritizationFrameworkType
  values: Record<string, string>
  category: MoscowCategory | null
  created_at: string
  updated_at: string
}

export interface ScenarioPriorityProjectComparison {
  project_id: string
  project_name: string
  has_override: boolean

  baseline_score: string | null
  baseline_rank: number | null
  baseline_category: MoscowCategory | null
  baseline_missing_criteria: string[]
  baseline_breakdown: Record<string, string>

  scenario_score: string | null
  scenario_rank: number | null
  scenario_category: MoscowCategory | null
  scenario_missing_criteria: string[]
  scenario_breakdown: Record<string, string>

  changed: boolean
}

export interface ScenarioPriorityComparison {
  scenario_id: string
  framework_id: string
  framework_name: string
  framework_type: PrioritizationFrameworkType
  has_changes: boolean
  items: ScenarioPriorityProjectComparison[]
}

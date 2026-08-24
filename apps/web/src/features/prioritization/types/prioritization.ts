/**
 * Mirrors apps/api/app/schemas/prioritization.py verbatim. v1 supports
 * only RICE and WEIGHTED (see app/models/enums.py::PrioritizationFrameworkType's
 * docstring — ICE/WSJF/MoSCoW are named in CLAUDE.md §18 as "may be
 * supported later" but have no formula built yet, see
 * docs/PRD-phase-17-prioritization.md).
 */

export type PrioritizationFrameworkType = 'rice' | 'weighted'

export interface PrioritizationCriterion {
  id: string
  key: string
  name: string
  weight: string | null
  is_editable: boolean
  sequence: number
}

export interface PrioritizationFramework {
  id: string
  organization_id: string
  name: string
  framework_type: PrioritizationFrameworkType
  is_active: boolean
  criteria: PrioritizationCriterion[]
  created_at: string
  updated_at: string
}

export interface ProjectPriorityScore {
  id: string
  project_id: string
  framework_id: string
  framework_name: string
  framework_type: PrioritizationFrameworkType
  /** A decimal-as-string, or null exactly when missing_criteria is
   * non-empty — never computed client-side, always exactly what the API
   * returned (CLAUDE.md §4: AI/frontend is never the source of truth for
   * a calculation). */
  score: string | null
  missing_criteria: string[]
  breakdown: Record<string, string>
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PortfolioRankingEntry {
  project_id: string
  project_name: string
  score: string | null
  rank: number | null
  missing_criteria: string[]
  breakdown: Record<string, string>
}

export interface PortfolioRanking {
  framework_id: string
  framework_name: string
  framework_type: PrioritizationFrameworkType
  items: PortfolioRankingEntry[]
}

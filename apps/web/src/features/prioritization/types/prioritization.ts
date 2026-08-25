/**
 * Mirrors apps/api/app/schemas/prioritization.py verbatim. Phase 18
 * completes the framework set CLAUDE.md §18 names: RICE, ICE, WSJF,
 * Weighted Scoring, and MoSCoW (see
 * app/models/enums.py::PrioritizationFrameworkType's docstring). MoSCoW
 * is deliberately categorical, never numeric — see
 * app/domain/prioritization.py::calculate_moscow_result's docstring.
 */

export type PrioritizationFrameworkType = 'rice' | 'ice' | 'wsjf' | 'moscow' | 'weighted'

export type MoscowCategory = 'must' | 'should' | 'could' | 'wont'

export type ProjectDependencyType = 'blocks' | 'related' | 'enables'

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
   * non-empty (or the framework is MoSCoW, which never produces a
   * number) — never computed client-side, always exactly what the API
   * returned (CLAUDE.md §4: AI/frontend is never the source of truth for
   * a calculation). */
  score: string | null
  missing_criteria: string[]
  breakdown: Record<string, string>
  /** Populated only for a MoSCoW-framework score. Null for every other
   * framework type. */
  category: MoscowCategory | null
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
  category: MoscowCategory | null
}

export interface PortfolioRanking {
  framework_id: string
  framework_name: string
  framework_type: PrioritizationFrameworkType
  items: PortfolioRankingEntry[]
}

export interface ProjectDependency {
  id: string
  from_project_id: string
  from_project_name: string
  to_project_id: string
  to_project_name: string
  dependency_type: ProjectDependencyType
  created_at: string
}

export interface DependencyGraphNode {
  project_id: string
  project_name: string
}

export interface DependencyGraph {
  nodes: DependencyGraphNode[]
  edges: ProjectDependency[]
}

export interface PortfolioSnapshotEntry {
  project_id: string
  project_name: string
  score: string | null
  rank: number | null
  missing_criteria: string[]
  breakdown: Record<string, string>
  category: MoscowCategory | null
}

export interface PortfolioSnapshot {
  id: string
  framework_id: string
  /** Frozen at capture time — NOT the framework's current (possibly
   * since-renamed) name. See app/models/portfolio_snapshot.py's
   * docstring for why a snapshot must never drift with a later edit. */
  framework_name: string
  framework_type: PrioritizationFrameworkType
  taken_at: string
  entries: PortfolioSnapshotEntry[]
}

/** Phase 22 — never persisted, computed fresh on every comparison read.
 * Mirrors app/domain/portfolio_snapshot.py::SnapshotComparisonStatus. */
export type SnapshotComparisonStatus = 'entered' | 'left' | 'changed' | 'unchanged'

export interface SnapshotComparisonItem {
  project_id: string
  project_name: string
  status: SnapshotComparisonStatus
  rank_from: number | null
  rank_to: number | null
  score_from: string | null
  score_to: string | null
  category_from: MoscowCategory | null
  category_to: MoscowCategory | null
}

export interface PortfolioSnapshotComparison {
  from_snapshot_id: string
  to_snapshot_id: string
  framework_id: string
  framework_name: string
  framework_type: PrioritizationFrameworkType
  items: SnapshotComparisonItem[]
}

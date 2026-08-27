import type { PortfolioRankingEntry, PrioritizationFrameworkType } from '../types/prioritization'

/**
 * Phase 27 — the PRD's §15 "Priority vs. Effort scatter" visualization,
 * built entirely from GET .../prioritization/portfolio (unchanged since
 * Phase 17) — no new backend endpoint. `effort` is copied verbatim from
 * each project's already-returned `breakdown`, never recomputed.
 *
 * Only RICE and WSJF carry a defined effort-like denominator —
 * `app/domain/prioritization.py::RICE_CRITERION_KEYS` names it "effort"
 * directly; `WSJF_CRITERION_KEYS` names the structurally analogous
 * concept "job_size" (the PRD's own §5.1 table lists both frameworks'
 * formulas as `(...) / <effort-like divisor>`). ICE has no such
 * denominator at all (`calculate_ice_score` is a plain average of
 * Impact/Confidence/Ease, never divided by anything) and Weighted
 * Scoring's criteria are fully organization-defined with no reliable
 * "effort" key — both are deliberately excluded rather than guessed at,
 * matching WSJF Breakdown's (Phase 25) own "no fabricated interpretation"
 * discipline. `priority` is each project's already-computed score,
 * copied verbatim — never recalculated here.
 */

export interface PriorityEffortPoint {
  project_id: string
  project_name: string
  effort: number
  priority: number
}

const EFFORT_CRITERION_KEY_BY_FRAMEWORK: Partial<Record<PrioritizationFrameworkType, string>> = {
  rice: 'effort',
  wsjf: 'job_size',
}

export function buildPriorityEffortScatter(
  frameworkType: PrioritizationFrameworkType,
  items: PortfolioRankingEntry[],
): PriorityEffortPoint[] {
  const effortKey = EFFORT_CRITERION_KEY_BY_FRAMEWORK[frameworkType]
  if (!effortKey) return []

  return items
    .filter((item) => item.score !== null && effortKey in item.breakdown)
    .map((item) => ({
      project_id: item.project_id,
      project_name: item.project_name,
      effort: Number(item.breakdown[effortKey]),
      priority: Number(item.score),
    }))
}

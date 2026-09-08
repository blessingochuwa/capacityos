import type { Risk } from '@/features/risks/types/risks'
import type { PortfolioRankingEntry } from '../types/prioritization'

/**
 * Phase 45 — the PRD's §15 "Risk vs. Value quadrant" visualization.
 * Answers: "which projects carry the most open risk relative to how
 * valuable they are?" Pure, DB-free reshaping of two already-authorized,
 * already-organization-scoped reads (GET /api/v1/prioritization/portfolio
 * and GET /api/v1/projects/{id}/risks, one call per project) — no new
 * backend endpoint, no new risk model, no new priority formula.
 *
 * VALUE DEFINITION (product decision, Phase 45 — explicitly confirmed by
 * the user, not derived by audit): a project's Value is its already-
 * computed priority score under the currently selected framework — the
 * exact same number the Capacity vs. Priority matrix (Phase 42) and
 * Priority vs. Effort scatter (Phase 27) already plot, copied verbatim,
 * never recalculated. `score === null` (incomplete numeric-framework
 * inputs, or any MoSCoW-scored project, which never produces a number at
 * all) means Value is missing; the project is excluded
 * (reason "no_priority_score"), the identical `score !== null` filter
 * every other prioritization chart in this codebase already uses.
 *
 * RISK DEFINITION (product decision, Phase 45 — explicitly confirmed by
 * the user): a project's Risk is the COUNT of its open (not `closed`)
 * Risk records whose derived `exposure` is `"high"` —
 * `countOpenHighExposureRisks` below reuses the exact condition
 * `app/domain/risk.py::classify_risk_signal` already uses to decide
 * whether a risk fires the existing `risk_high_exposure` Insights signal
 * (CLAUDE.md §17: "closing a risk is the explicit 'no longer live'
 * action" — a closed risk never counts, matching that established rule
 * verbatim). This is a plain count of an already-meaningful condition,
 * never a synthesized "risk score" — CLAUDE.md §17's "do not create risk
 * scores that imply false precision" is honored by counting, not scoring.
 *
 * A project's risk count is a REAL, always-computable fact once its risk
 * list has been successfully fetched — including a genuine `0` when it
 * has no open high-exposure risks (unlike Phase 42's capacity axis, an
 * empty risk list is not an ambiguous "never assessed" state; it is the
 * positive fact "no risk of this kind currently exists," the same fact
 * the Insights page already treats as "no signal fires"). Risk becomes
 * "missing" (reason "risk_data_unavailable") ONLY when that project's
 * risk list could not be fetched at all — the one genuine unknown this
 * axis can have.
 *
 * MEDIAN / QUADRANT RULE: reference lines are the median Risk count and
 * median Value across the CURRENTLY PLOTTED points only, never an
 * arbitrary invented threshold (CLAUDE.md §17/§29) — this reapplies
 * Phase 42's own median-line technique deliberately, not silently: it is
 * the only quadrant-boundary technique this codebase has ever used for a
 * descriptive prioritization quadrant, and no alternative was specified
 * for this chart. A value exactly equal to its axis's median belongs to
 * the "low"/"not above" side of that axis — the identical, explicitly
 * documented tie rule Phase 42 established, applied identically here.
 *
 * Quadrants are purely descriptive labels of relative position — never a
 * recommendation, priority ranking, or "kill/invest" judgment (CLAUDE.md
 * §17/§29).
 */

export type RiskValueQuadrant =
  | 'high_value_high_risk'
  | 'high_value_low_risk'
  | 'low_value_high_risk'
  | 'low_value_low_risk'

export const QUADRANT_LABEL: Record<RiskValueQuadrant, string> = {
  high_value_high_risk: 'High Value / High Risk',
  high_value_low_risk: 'High Value / Low Risk',
  low_value_high_risk: 'Low Value / High Risk',
  low_value_low_risk: 'Low Value / Low Risk',
}

export const QUADRANT_DESCRIPTION: Record<RiskValueQuadrant, string> = {
  high_value_high_risk: 'High value, above-median open high-exposure risk count.',
  high_value_low_risk: 'High value, at or below-median open high-exposure risk count.',
  low_value_high_risk: 'Lower value, above-median open high-exposure risk count.',
  low_value_low_risk: 'Lower value, at or below-median open high-exposure risk count.',
}

export interface RiskValuePoint {
  project_id: string
  project_name: string
  risk_count: number
  value_score: number
  quadrant: RiskValueQuadrant
}

export type RiskValueExclusionReason =
  | 'no_priority_score'
  | 'risk_data_unavailable'
  | 'no_priority_score_and_risk_data_unavailable'

export interface ExcludedRiskValueProject {
  project_id: string
  project_name: string
  reason: RiskValueExclusionReason
}

export interface RiskValueMatrixModel {
  points: RiskValuePoint[]
  excluded: ExcludedRiskValueProject[]
  /** Median across `points` only. Both null exactly when `points` is empty. */
  medianRisk: number | null
  medianValue: number | null
}

/** A project's open high-exposure risk count — every `Risk` row whose
 * `status` is not `"closed"` and whose `exposure` is `"high"`, mirroring
 * `app/domain/risk.py::classify_risk_signal`'s own condition for firing
 * the `risk_high_exposure` signal, verbatim. */
export function countOpenHighExposureRisks(risks: Risk[]): number {
  return risks.filter((risk) => risk.status !== 'closed' && risk.exposure === 'high').length
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid]
}

function byNameThenId(
  a: { project_name: string; project_id: string },
  b: { project_name: string; project_id: string },
): number {
  return a.project_name.localeCompare(b.project_name) || a.project_id.localeCompare(b.project_id)
}

export function buildRiskValueMatrix(
  items: PortfolioRankingEntry[],
  /** project_id -> open high-exposure risk count, present ONLY for a
   * project whose risk list was successfully fetched (a real `0` is a
   * valid entry; an absent key means the fetch failed or never
   * completed — see the module docstring). */
  riskCountsByProject: Map<string, number>,
): RiskValueMatrixModel {
  const plottable: { project_id: string; project_name: string; risk_count: number; value_score: number }[] = []
  const excluded: ExcludedRiskValueProject[] = []

  for (const item of items) {
    const risk_count = riskCountsByProject.get(item.project_id)
    const hasRisk = risk_count !== undefined
    const hasValue = item.score !== null

    if (hasRisk && hasValue) {
      plottable.push({
        project_id: item.project_id,
        project_name: item.project_name,
        risk_count,
        value_score: Number(item.score),
      })
    } else {
      const reason: RiskValueExclusionReason =
        !hasValue && !hasRisk
          ? 'no_priority_score_and_risk_data_unavailable'
          : !hasValue
            ? 'no_priority_score'
            : 'risk_data_unavailable'
      excluded.push({ project_id: item.project_id, project_name: item.project_name, reason })
    }
  }

  if (plottable.length === 0) {
    return {
      points: [],
      excluded: excluded.sort(byNameThenId),
      medianRisk: null,
      medianValue: null,
    }
  }

  const medianRisk = median(plottable.map((p) => p.risk_count))
  const medianValue = median(plottable.map((p) => p.value_score))

  const points: RiskValuePoint[] = plottable.map((p) => {
    const highRisk = p.risk_count > medianRisk
    const highValue = p.value_score > medianValue
    const quadrant: RiskValueQuadrant = highValue
      ? highRisk
        ? 'high_value_high_risk'
        : 'high_value_low_risk'
      : highRisk
        ? 'low_value_high_risk'
        : 'low_value_low_risk'
    return { ...p, quadrant }
  })

  points.sort(byNameThenId)

  return { points, excluded: excluded.sort(byNameThenId), medianRisk, medianValue }
}

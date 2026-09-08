import type { Allocation } from '@/types/entities'
import type { PortfolioRankingEntry } from '../types/prioritization'

/**
 * Phase 42 — the PRD's §15 "Capacity vs. Priority matrix" visualization.
 * Answers: "which projects have high priority relative to the capacity
 * required to deliver them?" Pure, DB-free reshaping of two already-
 * authorized, already-organization-scoped reads
 * (GET /api/v1/prioritization/portfolio and GET /api/v1/allocations) — no
 * new backend endpoint, no new capacity model, no new priority formula.
 *
 * CAPACITY DEFINITION (product decision, Phase 42 brief — do not reopen):
 * a project's capacity requirement is the sum of `allocation_hours` across
 * every `Allocation` currently recorded against it — "total allocated
 * hours over the currently represented planning horizon," using the
 * existing Allocation.allocation_hours semantic verbatim (no date window,
 * no forecasting, no per-period query). A project with at least one
 * recorded allocation gets a real, summed capacity value, including a
 * genuine 0.00 if every one of its allocations happens to be 0 hours. A
 * project with ZERO recorded allocations has no capacity data at all —
 * it is excluded (reason "no_capacity_data"), never plotted at a
 * fabricated x=0, since "never been allocated any hours" and "planned for
 * exactly zero hours" are not the same fact and this codebase has no
 * field that distinguishes them for an unallocated project (unlike
 * ProjectPriorityScore's own explicit `missing_criteria` field for
 * priority, allocations carry no analogous "not yet planned" marker — the
 * absence of any Allocation row IS that marker here).
 *
 * PRIORITY DEFINITION: each project's already-computed `score` from the
 * portfolio ranking for the currently selected framework — copied
 * verbatim, never recalculated (CLAUDE.md §4/§21). `score === null`
 * (incomplete numeric-framework inputs, or any MoSCoW-scored project,
 * which never produces a number at all — calculate_moscow_result) means
 * priority is missing; the project is excluded (reason
 * "no_priority_score"), exactly like every other prioritization chart in
 * this codebase (WsjfBreakdownChart, PriorityEffortScatterChart) already
 * filters on `score !== null`.
 *
 * MEDIAN / QUADRANT RULE (product decision, Phase 42 brief): reference
 * lines are the median capacity and median priority across the
 * CURRENTLY PLOTTED points only (never across excluded projects, which
 * have no comparable value) — never an arbitrary invented threshold
 * (CLAUDE.md §17/§29). A value exactly equal to its axis's median belongs
 * to the "low"/"not above median" side of that axis (a documented,
 * explicit tie rule, applied identically to both axes) — this is a
 * classification convention, not a magnitude judgment, and matches this
 * codebase's existing "existence gate, not invented threshold" discipline
 * (see docs/adr/0005-phase-5-operational-insights.md).
 *
 * Quadrants are purely descriptive labels of relative position — never a
 * recommendation, risk classification, or "good/bad/quick-win" judgment
 * (CLAUDE.md §17/§29's "no false precision"/"no misleading chart" rules).
 */

export type CapacityPriorityQuadrant =
  | 'high_priority_high_capacity'
  | 'high_priority_low_capacity'
  | 'low_priority_high_capacity'
  | 'low_priority_low_capacity'

export const QUADRANT_LABEL: Record<CapacityPriorityQuadrant, string> = {
  high_priority_high_capacity: 'High Priority / High Capacity',
  high_priority_low_capacity: 'High Priority / Low Capacity',
  low_priority_high_capacity: 'Low Priority / High Capacity',
  low_priority_low_capacity: 'Low Priority / Low Capacity',
}

export const QUADRANT_DESCRIPTION: Record<CapacityPriorityQuadrant, string> = {
  high_priority_high_capacity: 'High priority, requires above-median capacity.',
  high_priority_low_capacity: 'High priority, requires below-median (or median) capacity.',
  low_priority_high_capacity: 'Lower priority, requires above-median capacity.',
  low_priority_low_capacity: 'Lower priority, requires below-median (or median) capacity.',
}

export interface CapacityPriorityPoint {
  project_id: string
  project_name: string
  capacity_hours: number
  priority_score: number
  quadrant: CapacityPriorityQuadrant
}

export type CapacityPriorityExclusionReason =
  | 'no_priority_score'
  | 'no_capacity_data'
  | 'no_priority_score_and_no_capacity_data'

export interface ExcludedCapacityPriorityProject {
  project_id: string
  project_name: string
  reason: CapacityPriorityExclusionReason
}

export interface CapacityPriorityMatrixModel {
  points: CapacityPriorityPoint[]
  excluded: ExcludedCapacityPriorityProject[]
  /** Median across `points` only. Both null exactly when `points` is empty. */
  medianCapacity: number | null
  medianPriority: number | null
}

/** Sorted-array midpoint — average of the two middle values for an even
 * count, the single middle value for an odd count. Deterministic for a
 * given input regardless of input order. */
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

export function buildCapacityPriorityMatrix(
  items: PortfolioRankingEntry[],
  allocations: Allocation[],
): CapacityPriorityMatrixModel {
  const capacityByProject = new Map<string, number>()
  for (const allocation of allocations) {
    const current = capacityByProject.get(allocation.project_id) ?? 0
    capacityByProject.set(allocation.project_id, current + Number(allocation.allocation_hours))
  }

  const plottable: { project_id: string; project_name: string; capacity_hours: number; priority_score: number }[] = []
  const excluded: ExcludedCapacityPriorityProject[] = []

  for (const item of items) {
    const capacity_hours = capacityByProject.get(item.project_id)
    const hasCapacity = capacity_hours !== undefined
    const hasPriority = item.score !== null

    if (hasCapacity && hasPriority) {
      plottable.push({
        project_id: item.project_id,
        project_name: item.project_name,
        capacity_hours,
        priority_score: Number(item.score),
      })
    } else {
      const reason: CapacityPriorityExclusionReason =
        !hasPriority && !hasCapacity
          ? 'no_priority_score_and_no_capacity_data'
          : !hasPriority
            ? 'no_priority_score'
            : 'no_capacity_data'
      excluded.push({ project_id: item.project_id, project_name: item.project_name, reason })
    }
  }

  if (plottable.length === 0) {
    return {
      points: [],
      excluded: excluded.sort(byNameThenId),
      medianCapacity: null,
      medianPriority: null,
    }
  }

  const medianCapacity = median(plottable.map((p) => p.capacity_hours))
  const medianPriority = median(plottable.map((p) => p.priority_score))

  const points: CapacityPriorityPoint[] = plottable.map((p) => {
    const highCapacity = p.capacity_hours > medianCapacity
    const highPriority = p.priority_score > medianPriority
    const quadrant: CapacityPriorityQuadrant = highPriority
      ? highCapacity
        ? 'high_priority_high_capacity'
        : 'high_priority_low_capacity'
      : highCapacity
        ? 'low_priority_high_capacity'
        : 'low_priority_low_capacity'
    return { ...p, quadrant }
  })

  points.sort(byNameThenId)

  return { points, excluded: excluded.sort(byNameThenId), medianCapacity, medianPriority }
}

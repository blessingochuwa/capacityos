import type { Project } from '@/types/entities'
import type { DependencyGraph } from '../types/prioritization'

/**
 * Phase 40 — the PRD's §15 "Dependency timeline" visualization. Pure,
 * DB-free reshaping of two already-authorized, already-organization-scoped
 * reads (GET /api/v1/projects and GET
 * /api/v1/prioritization/dependency-graph) into a schedule-ordered model.
 * Never fabricates a value:
 *
 *   - Timeline span is each project's own `start_date` -> `end_date`
 *     (Project schema, verbatim). A project is "scheduled" only when
 *     BOTH dates are present — a project missing either is placed in the
 *     separate `unscheduled` list, never given an invented date or
 *     position (Phase 39 decision).
 *   - Only `blocks` edges are represented (`related`/`enables` excluded).
 *     `blocked_by` is not synthesised — it is only ever the inverse read
 *     of a `blocks` edge (ProjectDependency's own model docstring), so
 *     adding it here would risk two directions that can disagree.
 *   - No schedule-consistency judgement is computed (a `blocks`
 *     predecessor whose dates fall after its successor's is NOT flagged)
 *     — that is a separate product rule not requested for this phase
 *     (CLAUDE.md §17/§29: do not invent a magnitude/consistency judgement
 *     for display).
 *
 * Ordering is fully deterministic so the same inputs always render the
 * same rows in the same order (mirrors compare_snapshot_entries' own
 * discipline).
 */

export interface ScheduledProjectRow {
  project_id: string
  project_name: string
  /** ISO date (YYYY-MM-DD), guaranteed non-null for a scheduled row. */
  start_date: string
  /** ISO date (YYYY-MM-DD), guaranteed non-null for a scheduled row. */
  end_date: string
}

export type UnscheduledReason = 'no_start_date' | 'no_end_date' | 'no_dates'

export interface UnscheduledProjectRow {
  project_id: string
  project_name: string
  status: Project['status']
  reason: UnscheduledReason
}

export interface BlocksEdgeRow {
  id: string
  from_project_id: string
  from_project_name: string
  to_project_id: string
  to_project_name: string
  /** True only when BOTH endpoints appear in `scheduled`. When false the
   * relationship is still shown (in text), but no timeline position is
   * implied for the unscheduled side. */
  both_scheduled: boolean
}

export interface DependencyTimelineModel {
  scheduled: ScheduledProjectRow[]
  unscheduled: UnscheduledProjectRow[]
  blocksEdges: BlocksEdgeRow[]
  /** Earliest `start_date` / latest `end_date` across `scheduled`, for a
   * chart axis domain. Both null exactly when `scheduled` is empty. */
  rangeStart: string | null
  rangeEnd: string | null
}

function unscheduledReason(project: Project): UnscheduledReason {
  if (!project.start_date && !project.end_date) return 'no_dates'
  if (!project.start_date) return 'no_start_date'
  return 'no_end_date'
}

function byNameThenId(
  a: { project_name: string; project_id: string },
  b: { project_name: string; project_id: string },
): number {
  return a.project_name.localeCompare(b.project_name) || a.project_id.localeCompare(b.project_id)
}

export function buildDependencyTimeline(
  projects: Project[],
  graph: DependencyGraph,
): DependencyTimelineModel {
  const scheduled: ScheduledProjectRow[] = []
  const unscheduled: UnscheduledProjectRow[] = []

  for (const project of projects) {
    if (project.start_date && project.end_date) {
      scheduled.push({
        project_id: project.id,
        project_name: project.name,
        start_date: project.start_date,
        end_date: project.end_date,
      })
    } else {
      unscheduled.push({
        project_id: project.id,
        project_name: project.name,
        status: project.status,
        reason: unscheduledReason(project),
      })
    }
  }

  scheduled.sort(
    (a, b) =>
      a.start_date.localeCompare(b.start_date) ||
      a.end_date.localeCompare(b.end_date) ||
      byNameThenId(a, b),
  )
  unscheduled.sort(byNameThenId)

  const scheduledIds = new Set(scheduled.map((row) => row.project_id))

  const blocksEdges: BlocksEdgeRow[] = graph.edges
    .filter((edge) => edge.dependency_type === 'blocks')
    .map((edge) => ({
      id: edge.id,
      from_project_id: edge.from_project_id,
      from_project_name: edge.from_project_name,
      to_project_id: edge.to_project_id,
      to_project_name: edge.to_project_name,
      both_scheduled:
        scheduledIds.has(edge.from_project_id) && scheduledIds.has(edge.to_project_id),
    }))
    .sort(
      (a, b) =>
        a.from_project_name.localeCompare(b.from_project_name) ||
        a.to_project_name.localeCompare(b.to_project_name) ||
        a.id.localeCompare(b.id),
    )

  const rangeStart = scheduled.length
    ? scheduled.reduce((min, row) => (row.start_date < min ? row.start_date : min), scheduled[0].start_date)
    : null
  const rangeEnd = scheduled.length
    ? scheduled.reduce((max, row) => (row.end_date > max ? row.end_date : max), scheduled[0].end_date)
    : null

  return { scheduled, unscheduled, blocksEdges, rangeStart, rangeEnd }
}

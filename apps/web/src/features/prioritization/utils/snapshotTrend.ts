import type { PortfolioSnapshot } from '../types/prioritization'

/**
 * Phase 24 — pure, DB-free reshaping of already-frozen Phase 21 snapshots
 * into a per-project score-over-time series. Mirrors
 * app/domain/portfolio_snapshot.py::compare_snapshot_entries's own
 * discipline, translated to the frontend: never recomputes a score, rank,
 * or category, and never fabricates a value for a snapshot where a
 * project has none — a project entering/leaving the portfolio, or a
 * MoSCoW snapshot (which never has a numeric score at all, only a
 * category — see app/domain/prioritization.py::calculate_moscow_result),
 * is represented as a gap (`null`), never interpolated or defaulted to
 * zero. Consumes exactly what GET /api/v1/prioritization/snapshots
 * already returns — no new backend endpoint exists or is needed for this.
 */

export interface SnapshotTrendProject {
  project_id: string
  project_name: string
}

export interface SnapshotTrendRow {
  snapshot_id: string
  taken_at: string
  [project_id: string]: string | number | null
}

export interface SnapshotTrendData {
  projects: SnapshotTrendProject[]
  rows: SnapshotTrendRow[]
}

export function buildSnapshotTrend(snapshots: PortfolioSnapshot[]): SnapshotTrendData {
  // Repeated/duplicate selection collapses to one point per snapshot id.
  const byId = new Map<string, PortfolioSnapshot>()
  for (const snapshot of snapshots) {
    byId.set(snapshot.id, snapshot)
  }
  const sorted = [...byId.values()].sort(
    (a, b) => new Date(a.taken_at).getTime() - new Date(b.taken_at).getTime(),
  )

  // Only projects that have a numeric score in at least one selected
  // snapshot are trendable at all (a MoSCoW category is never coerced
  // onto a numeric axis — CLAUDE.md §17's "no false precision"). Prefers
  // the chronologically latest snapshot's frozen project_name, matching
  // compare_snapshot_entries's own "prefer the `to` side" precedent.
  const projectNames = new Map<string, string>()
  for (const snapshot of sorted) {
    for (const entry of snapshot.entries) {
      if (entry.score !== null) {
        projectNames.set(entry.project_id, entry.project_name)
      }
    }
  }

  const rows: SnapshotTrendRow[] = sorted.map((snapshot) => {
    const row: SnapshotTrendRow = { snapshot_id: snapshot.id, taken_at: snapshot.taken_at }
    for (const projectId of projectNames.keys()) {
      row[projectId] = null
    }
    for (const entry of snapshot.entries) {
      if (entry.score !== null && projectNames.has(entry.project_id)) {
        row[entry.project_id] = Number(entry.score)
      }
    }
    return row
  })

  const projects: SnapshotTrendProject[] = [...projectNames.entries()].map(
    ([project_id, project_name]) => ({ project_id, project_name }),
  )

  return { projects, rows }
}

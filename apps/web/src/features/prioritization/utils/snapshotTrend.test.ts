import { describe, expect, it } from 'vitest'
import { buildSnapshotTrend } from './snapshotTrend'
import { makePortfolioSnapshot, makePortfolioRankingEntry } from '@/test/fixtures'

describe('buildSnapshotTrend', () => {
  it('builds one row per snapshot, sorted chronologically regardless of input order', () => {
    const early = makePortfolioSnapshot({ id: 'snap-early', taken_at: '2026-08-01T00:00:00Z' })
    const late = makePortfolioSnapshot({ id: 'snap-late', taken_at: '2026-08-15T00:00:00Z' })

    const { rows } = buildSnapshotTrend([late, early])

    expect(rows.map((r) => r.snapshot_id)).toEqual(['snap-early', 'snap-late'])
  })

  it('plots a project score at each snapshot where it was recorded', () => {
    const snapshot = makePortfolioSnapshot({
      entries: [makePortfolioRankingEntry({ project_id: 'p1', score: '400.00' })],
    })

    const { projects, rows } = buildSnapshotTrend([snapshot])

    expect(projects).toEqual([{ project_id: 'p1', project_name: 'Website Redesign' }])
    expect(rows[0].p1).toBe(400)
  })

  it('collapses a duplicate/repeated snapshot selection to a single point', () => {
    const snapshot = makePortfolioSnapshot({ id: 'snap-1' })

    const { rows } = buildSnapshotTrend([snapshot, snapshot, snapshot])

    expect(rows).toHaveLength(1)
  })

  it('represents a project entering the portfolio as a gap before it existed, not a fabricated value', () => {
    const before = makePortfolioSnapshot({
      id: 'snap-before',
      taken_at: '2026-08-01T00:00:00Z',
      entries: [makePortfolioRankingEntry({ project_id: 'p1', score: '400.00' })],
    })
    const after = makePortfolioSnapshot({
      id: 'snap-after',
      taken_at: '2026-08-15T00:00:00Z',
      entries: [
        makePortfolioRankingEntry({ project_id: 'p1', score: '400.00' }),
        makePortfolioRankingEntry({
          project_id: 'p2',
          project_name: 'New Project',
          score: '900.00',
        }),
      ],
    })

    const { rows } = buildSnapshotTrend([before, after])

    expect(rows[0].p2).toBeNull()
    expect(rows[1].p2).toBe(900)
  })

  it('represents a project leaving the portfolio as a gap after it left, not a fabricated value', () => {
    const before = makePortfolioSnapshot({
      id: 'snap-before',
      taken_at: '2026-08-01T00:00:00Z',
      entries: [makePortfolioRankingEntry({ project_id: 'p1', score: '400.00' })],
    })
    const after = makePortfolioSnapshot({
      id: 'snap-after',
      taken_at: '2026-08-15T00:00:00Z',
      entries: [],
    })

    const { rows } = buildSnapshotTrend([before, after])

    expect(rows[0].p1).toBe(400)
    expect(rows[1].p1).toBeNull()
  })

  it('produces no trendable projects when every entry has no numeric score (e.g. MoSCoW)', () => {
    const snapshot = makePortfolioSnapshot({
      framework_type: 'moscow',
      entries: [makePortfolioRankingEntry({ score: null, category: 'must' })],
    })

    const { projects, rows } = buildSnapshotTrend([snapshot])

    expect(projects).toEqual([])
    expect(rows[0]).toEqual({ snapshot_id: snapshot.id, taken_at: snapshot.taken_at })
  })

  it('prefers the chronologically latest snapshot for a project name that was renamed between snapshots', () => {
    const before = makePortfolioSnapshot({
      id: 'snap-before',
      taken_at: '2026-08-01T00:00:00Z',
      entries: [makePortfolioRankingEntry({ project_id: 'p1', project_name: 'Old Name' })],
    })
    const after = makePortfolioSnapshot({
      id: 'snap-after',
      taken_at: '2026-08-15T00:00:00Z',
      entries: [makePortfolioRankingEntry({ project_id: 'p1', project_name: 'New Name' })],
    })

    const { projects } = buildSnapshotTrend([before, after])

    expect(projects).toEqual([{ project_id: 'p1', project_name: 'New Name' }])
  })

  it('never mutates the snapshots it was given', () => {
    const snapshot = makePortfolioSnapshot()
    const before = JSON.parse(JSON.stringify(snapshot))

    buildSnapshotTrend([snapshot])

    expect(snapshot).toEqual(before)
  })
})

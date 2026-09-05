import { describe, expect, it } from 'vitest'
import { buildDependencyTimeline } from './dependencyTimeline'
import { makeDependencyGraph, makeProject, makeProjectDependency } from '@/test/fixtures'

describe('buildDependencyTimeline', () => {
  const emptyGraph = { nodes: [], edges: [] }

  it('returns an empty model for no projects', () => {
    expect(buildDependencyTimeline([], emptyGraph)).toEqual({
      scheduled: [],
      unscheduled: [],
      blocksEdges: [],
      rangeStart: null,
      rangeEnd: null,
    })
  })

  it('places a fully-dated project on the timeline with its dates verbatim', () => {
    const project = makeProject({
      id: 'p1',
      name: 'Website Redesign',
      start_date: '2026-09-01',
      end_date: '2026-10-15',
    })

    const model = buildDependencyTimeline([project], emptyGraph)

    expect(model.scheduled).toEqual([
      {
        project_id: 'p1',
        project_name: 'Website Redesign',
        start_date: '2026-09-01',
        end_date: '2026-10-15',
      },
    ])
    expect(model.unscheduled).toEqual([])
    expect(model.rangeStart).toBe('2026-09-01')
    expect(model.rangeEnd).toBe('2026-10-15')
  })

  it('orders scheduled projects deterministically by start, then end, then name', () => {
    const projects = [
      makeProject({ id: 'c', name: 'Charlie', start_date: '2026-09-10', end_date: '2026-09-20' }),
      makeProject({ id: 'a', name: 'Alpha', start_date: '2026-09-01', end_date: '2026-09-30' }),
      makeProject({ id: 'b', name: 'Bravo', start_date: '2026-09-01', end_date: '2026-09-15' }),
    ]

    const model = buildDependencyTimeline(projects, emptyGraph)

    expect(model.scheduled.map((row) => row.project_id)).toEqual(['b', 'a', 'c'])
    expect(model.rangeStart).toBe('2026-09-01')
    expect(model.rangeEnd).toBe('2026-09-30')
  })

  it('routes a project missing its start date to the unscheduled list with no fabricated dates', () => {
    const project = makeProject({
      id: 'p1',
      name: 'Planned Thing',
      status: 'planned',
      start_date: null,
      end_date: '2026-12-01',
    })

    const model = buildDependencyTimeline([project], emptyGraph)

    expect(model.scheduled).toEqual([])
    expect(model.unscheduled).toEqual([
      { project_id: 'p1', project_name: 'Planned Thing', status: 'planned', reason: 'no_start_date' },
    ])
    // No date-shaped keys leak onto an unscheduled row.
    expect(Object.keys(model.unscheduled[0])).toEqual([
      'project_id',
      'project_name',
      'status',
      'reason',
    ])
    expect(model.rangeStart).toBeNull()
    expect(model.rangeEnd).toBeNull()
  })

  it('classifies the missing-date reason (end / both)', () => {
    const noEnd = makeProject({ id: 'e', name: 'NoEnd', start_date: '2026-09-01', end_date: null })
    const noDates = makeProject({ id: 'n', name: 'NoDates', start_date: null, end_date: null })

    const model = buildDependencyTimeline([noEnd, noDates], emptyGraph)

    // Sorted by name: "NoDates" < "NoEnd".
    expect(model.unscheduled.map((r) => [r.project_id, r.reason])).toEqual([
      ['n', 'no_dates'],
      ['e', 'no_end_date'],
    ])
  })

  it('includes only blocks edges — related and enables are excluded', () => {
    const projects = [
      makeProject({ id: 'p1', name: 'A', start_date: '2026-09-01', end_date: '2026-09-10' }),
      makeProject({ id: 'p2', name: 'B', start_date: '2026-09-11', end_date: '2026-09-20' }),
    ]
    const graph = makeDependencyGraph({
      edges: [
        makeProjectDependency({
          id: 'e-blocks',
          from_project_id: 'p1',
          from_project_name: 'A',
          to_project_id: 'p2',
          to_project_name: 'B',
          dependency_type: 'blocks',
        }),
        makeProjectDependency({ id: 'e-related', dependency_type: 'related' }),
        makeProjectDependency({ id: 'e-enables', dependency_type: 'enables' }),
      ],
    })

    const model = buildDependencyTimeline(projects, graph)

    expect(model.blocksEdges).toEqual([
      {
        id: 'e-blocks',
        from_project_id: 'p1',
        from_project_name: 'A',
        to_project_id: 'p2',
        to_project_name: 'B',
        both_scheduled: true,
      },
    ])
  })

  it('flags a blocks edge whose endpoint is unscheduled without inventing a position', () => {
    const projects = [
      makeProject({ id: 'p1', name: 'Scheduled', start_date: '2026-09-01', end_date: '2026-09-10' }),
      makeProject({ id: 'p2', name: 'Undated', start_date: null, end_date: null }),
    ]
    const graph = makeDependencyGraph({
      edges: [
        makeProjectDependency({
          id: 'e1',
          from_project_id: 'p1',
          from_project_name: 'Scheduled',
          to_project_id: 'p2',
          to_project_name: 'Undated',
          dependency_type: 'blocks',
        }),
      ],
    })

    const model = buildDependencyTimeline(projects, graph)

    expect(model.blocksEdges).toHaveLength(1)
    expect(model.blocksEdges[0].both_scheduled).toBe(false)
    expect(model.scheduled.map((r) => r.project_id)).toEqual(['p1'])
  })

  it('orders blocks edges deterministically by from-name, to-name, id', () => {
    const graph = makeDependencyGraph({
      edges: [
        makeProjectDependency({ id: 'z', from_project_name: 'Beta', to_project_name: 'Zed', dependency_type: 'blocks' }),
        makeProjectDependency({ id: 'a', from_project_name: 'Alpha', to_project_name: 'Yak', dependency_type: 'blocks' }),
        makeProjectDependency({ id: 'b', from_project_name: 'Alpha', to_project_name: 'Ack', dependency_type: 'blocks' }),
      ],
    })

    const model = buildDependencyTimeline([], graph)

    expect(model.blocksEdges.map((e) => e.id)).toEqual(['b', 'a', 'z'])
  })

  it('renders a timeline with projects but no dependencies (not an error state)', () => {
    const projects = [
      makeProject({ id: 'p1', name: 'A', start_date: '2026-09-01', end_date: '2026-09-10' }),
    ]

    const model = buildDependencyTimeline(projects, emptyGraph)

    expect(model.scheduled).toHaveLength(1)
    expect(model.blocksEdges).toEqual([])
  })

  it('reflects only the projects it is given — an edge to an unknown project pulls in no row', () => {
    const projects = [
      makeProject({ id: 'p1', name: 'A', start_date: '2026-09-01', end_date: '2026-09-10' }),
    ]
    const graph = makeDependencyGraph({
      edges: [
        makeProjectDependency({
          id: 'e1',
          from_project_id: 'p1',
          from_project_name: 'A',
          to_project_id: 'ghost',
          to_project_name: 'Ghost In Another Org',
          dependency_type: 'blocks',
        }),
      ],
    })

    const model = buildDependencyTimeline(projects, graph)

    expect(model.scheduled.map((r) => r.project_id)).toEqual(['p1'])
    expect(model.unscheduled).toEqual([])
    expect(model.blocksEdges[0].both_scheduled).toBe(false)
  })
})

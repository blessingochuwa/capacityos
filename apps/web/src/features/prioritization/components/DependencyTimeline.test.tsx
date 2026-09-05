import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { DependencyTimeline } from './DependencyTimeline'
import { makeDependencyGraph, makeProject, makeProjectDependency } from '@/test/fixtures'

const emptyGraph = { nodes: [], edges: [] }

describe('DependencyTimeline', () => {
  it('shows an empty state when there are no projects', () => {
    render(<DependencyTimeline projects={[]} graph={emptyGraph} />)
    expect(screen.getByText('No projects yet.')).toBeInTheDocument()
  })

  it('renders scheduled projects with their start and end dates', () => {
    const projects = [
      makeProject({
        id: 'p1',
        name: 'Website Redesign',
        start_date: '2026-09-01',
        end_date: '2026-10-15',
      }),
    ]
    render(<DependencyTimeline projects={projects} graph={emptyGraph} />)

    const table = screen.getByRole('table', {
      name: 'Scheduled projects on the dependency timeline',
    })
    const row = within(table).getByText('Website Redesign').closest('tr')
    expect(row).not.toBeNull()
    expect(row?.textContent).toContain('2026')
    expect(row?.textContent).toContain('Sep')
    expect(row?.textContent).toContain('Oct')
  })

  it('renders multiple scheduled projects in deterministic start-date order', () => {
    const projects = [
      makeProject({ id: 'b', name: 'Second', start_date: '2026-10-01', end_date: '2026-10-10' }),
      makeProject({ id: 'a', name: 'First', start_date: '2026-09-01', end_date: '2026-09-10' }),
    ]
    render(<DependencyTimeline projects={projects} graph={emptyGraph} />)

    const table = screen.getByRole('table', {
      name: 'Scheduled projects on the dependency timeline',
    })
    const names = within(table)
      .getAllByRole('row')
      .slice(1)
      .map((tr) => tr.querySelector('td')?.textContent)
    expect(names).toEqual(['First', 'Second'])
  })

  it('lists undated projects in a separate Unscheduled section, not on the timeline', () => {
    const projects = [
      makeProject({ id: 'p1', name: 'Scheduled One', start_date: '2026-09-01', end_date: '2026-09-30' }),
      makeProject({ id: 'p2', name: 'Undated Two', status: 'planned', start_date: null, end_date: null }),
    ]
    render(<DependencyTimeline projects={projects} graph={emptyGraph} />)

    const scheduledTable = screen.getByRole('table', {
      name: 'Scheduled projects on the dependency timeline',
    })
    expect(within(scheduledTable).queryByText('Undated Two')).toBeNull()

    const unscheduledTable = screen.getByRole('table', {
      name: 'Projects with no scheduled span',
    })
    const row = within(unscheduledTable).getByText('Undated Two').closest('tr')
    expect(row?.textContent).toContain('No start or end date')
  })

  it('shows the "no scheduled projects" message when every project is undated', () => {
    const projects = [
      makeProject({ id: 'p1', name: 'Planned A', start_date: null, end_date: null }),
      makeProject({ id: 'p2', name: 'Planned B', start_date: '2026-09-01', end_date: null }),
    ]
    render(<DependencyTimeline projects={projects} graph={emptyGraph} />)

    expect(
      screen.getByText(/No scheduled projects yet\./),
    ).toBeInTheDocument()
    const unscheduledTable = screen.getByRole('table', {
      name: 'Projects with no scheduled span',
    })
    expect(within(unscheduledTable).getByText('Planned A')).toBeInTheDocument()
    expect(within(unscheduledTable).getByText('Planned B')).toBeInTheDocument()
  })

  it('represents a blocks relationship with both project names and direction', () => {
    const projects = [
      makeProject({ id: 'p1', name: 'Design System', start_date: '2026-09-01', end_date: '2026-09-20' }),
      makeProject({ id: 'p2', name: 'Marketing Site', start_date: '2026-09-21', end_date: '2026-10-10' }),
    ]
    const graph = makeDependencyGraph({
      edges: [
        makeProjectDependency({
          id: 'e1',
          from_project_id: 'p1',
          from_project_name: 'Design System',
          to_project_id: 'p2',
          to_project_name: 'Marketing Site',
          dependency_type: 'blocks',
        }),
      ],
    })
    render(<DependencyTimeline projects={projects} graph={graph} />)

    const table = screen.getByRole('table', {
      name: 'Blocking relationships between projects',
    })
    const row = within(table).getByText('Design System').closest('tr')
    expect(row?.textContent).toContain('blocks')
    expect(row?.textContent).toContain('Marketing Site')
    expect(row?.textContent).toContain('Both scheduled')
  })

  it('excludes non-blocks dependency types from the relationships table', () => {
    const projects = [
      makeProject({ id: 'p1', name: 'A', start_date: '2026-09-01', end_date: '2026-09-10' }),
    ]
    const graph = makeDependencyGraph({
      edges: [
        makeProjectDependency({ id: 'r1', from_project_name: 'Rel From', to_project_name: 'Rel To', dependency_type: 'related' }),
        makeProjectDependency({ id: 'n1', from_project_name: 'Ena From', to_project_name: 'Ena To', dependency_type: 'enables' }),
      ],
    })
    render(<DependencyTimeline projects={projects} graph={graph} />)

    expect(screen.getByText('No blocking relationships recorded.')).toBeInTheDocument()
    expect(screen.queryByText('Rel From')).toBeNull()
    expect(screen.queryByText('Ena From')).toBeNull()
  })

  it('marks a blocks relationship that involves an unscheduled project', () => {
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
    render(<DependencyTimeline projects={projects} graph={graph} />)

    const table = screen.getByRole('table', {
      name: 'Blocking relationships between projects',
    })
    expect(within(table).getByText('Involves an unscheduled project')).toBeInTheDocument()
  })

  it('renders normally when there are scheduled projects but no dependencies', () => {
    const projects = [
      makeProject({ id: 'p1', name: 'Solo Project', start_date: '2026-09-01', end_date: '2026-09-10' }),
    ]
    render(<DependencyTimeline projects={projects} graph={emptyGraph} />)

    expect(
      screen.getByRole('table', { name: 'Scheduled projects on the dependency timeline' }),
    ).toBeInTheDocument()
    expect(screen.getByText('No blocking relationships recorded.')).toBeInTheDocument()
    expect(screen.queryByText('No projects yet.')).toBeNull()
  })
})

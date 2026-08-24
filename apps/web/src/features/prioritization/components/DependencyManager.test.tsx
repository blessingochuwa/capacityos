import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DependencyManager } from './DependencyManager'
import { useProjects } from '@/hooks/useProjects'
import { useCreateDependency, useDeleteDependency } from '../hooks/useDependencyMutations'
import { useProjectDependencies } from '../hooks/useProjectDependencies'
import { makeProject, makeProjectDependency } from '@/test/fixtures'
import { mockQuerySuccess } from '@/test/mockQueryResult'

vi.mock('@/hooks/useProjects')
vi.mock('../hooks/useDependencyMutations')
vi.mock('../hooks/useProjectDependencies')

const mockedUseProjects = vi.mocked(useProjects)
const mockedUseCreateDependency = vi.mocked(useCreateDependency)
const mockedUseDeleteDependency = vi.mocked(useDeleteDependency)
const mockedUseProjectDependencies = vi.mocked(useProjectDependencies)

function mockMutations(overrides: {
  create?: Record<string, unknown>
  remove?: Record<string, unknown>
} = {}) {
  mockedUseCreateDependency.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.create,
  } as unknown as ReturnType<typeof useCreateDependency>)
  mockedUseDeleteDependency.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.remove,
  } as unknown as ReturnType<typeof useDeleteDependency>)
}

const projects = [
  makeProject({ id: 'project-1', name: 'Website Redesign' }),
  makeProject({ id: 'project-2', name: 'Mobile App' }),
]

describe('DependencyManager', () => {
  it('prompts for a project before showing any dependency management UI', () => {
    mockMutations()
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: projects, total: 2 }))
    mockedUseProjectDependencies.mockReturnValue(mockQuerySuccess([]))
    render(
      <DependencyManager canManage={true} fromProjectId={undefined} onFromProjectChange={vi.fn()} />,
    )
    expect(screen.queryByText(/no recorded dependencies/i)).not.toBeInTheDocument()
  })

  it('creates a dependency for the selected project', async () => {
    const mutate = vi.fn()
    mockMutations({ create: { mutate } })
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: projects, total: 2 }))
    mockedUseProjectDependencies.mockReturnValue(mockQuerySuccess([]))
    const user = userEvent.setup()
    render(
      <DependencyManager
        canManage={true}
        fromProjectId="project-1"
        onFromProjectChange={vi.fn()}
      />,
    )

    await user.selectOptions(screen.getByLabelText('Depends on / relates to'), 'project-2')
    await user.selectOptions(screen.getByLabelText('Relationship'), 'blocks')
    await user.click(screen.getByRole('button', { name: /add dependency/i }))

    expect(mutate).toHaveBeenCalledWith(
      { to_project_id: 'project-2', dependency_type: 'blocks' },
      expect.anything(),
    )
  })

  it('shows existing dependencies and lets the owning project remove one', async () => {
    const mutate = vi.fn()
    mockMutations({ remove: { mutate } })
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: projects, total: 2 }))
    mockedUseProjectDependencies.mockReturnValue(
      mockQuerySuccess([
        makeProjectDependency({
          id: 'dep-1',
          from_project_id: 'project-1',
          from_project_name: 'Website Redesign',
          to_project_id: 'project-2',
          to_project_name: 'Mobile App',
        }),
      ]),
    )
    const user = userEvent.setup()
    render(
      <DependencyManager
        canManage={true}
        fromProjectId="project-1"
        onFromProjectChange={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: /remove/i }))
    expect(mutate).toHaveBeenCalledWith('dep-1')
  })

  it('hides the create form and remove actions when the caller cannot manage dependencies', () => {
    mockMutations()
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: projects, total: 2 }))
    mockedUseProjectDependencies.mockReturnValue(
      mockQuerySuccess([makeProjectDependency({ from_project_id: 'project-1' })]),
    )
    render(
      <DependencyManager
        canManage={false}
        fromProjectId="project-1"
        onFromProjectChange={vi.fn()}
      />,
    )
    expect(screen.queryByLabelText('Depends on / relates to')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument()
  })
})

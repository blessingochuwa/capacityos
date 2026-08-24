import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PriorityOverrideForm } from './PriorityOverrideForm'
import { useFrameworks } from '@/features/prioritization/hooks/useFrameworks'
import { useProjects } from '@/hooks/useProjects'
import { useSetScenarioPriorityOverride } from '../hooks/useScenarioPriorityOverrideMutations'
import { makePrioritizationFramework, makeProject } from '@/test/fixtures'
import { mockQuerySuccess } from '@/test/mockQueryResult'

vi.mock('@/features/prioritization/hooks/useFrameworks')
vi.mock('@/hooks/useProjects')
vi.mock('../hooks/useScenarioPriorityOverrideMutations')

const mockedUseFrameworks = vi.mocked(useFrameworks)
const mockedUseProjects = vi.mocked(useProjects)
const mockedUseSetOverride = vi.mocked(useSetScenarioPriorityOverride)

function mockMutation(overrides: Record<string, unknown> = {}) {
  mockedUseSetOverride.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides,
  } as unknown as ReturnType<typeof useSetScenarioPriorityOverride>)
}

const project = makeProject({ id: 'project-1', name: 'Website Redesign' })
const riceFramework = makePrioritizationFramework({ id: 'framework-1', framework_type: 'rice' })
const moscowFramework = makePrioritizationFramework({
  id: 'framework-2',
  name: 'Release MoSCoW',
  framework_type: 'moscow',
  criteria: [],
})

describe('PriorityOverrideForm', () => {
  it('renders one criterion input per framework criterion for a numeric framework', async () => {
    mockMutation()
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [project], total: 1 }))
    mockedUseFrameworks.mockReturnValue(
      mockQuerySuccess({ items: [riceFramework], total: 1 }),
    )
    const user = userEvent.setup()
    render(<PriorityOverrideForm scenarioId="scenario-1" />)

    await user.selectOptions(screen.getByLabelText('Override framework'), 'framework-1')
    expect(screen.getByLabelText('Reach')).toBeInTheDocument()
    expect(screen.getByLabelText('Effort')).toBeInTheDocument()
  })

  it('shows a category selector instead of criterion inputs for MoSCoW', async () => {
    mockMutation()
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [project], total: 1 }))
    mockedUseFrameworks.mockReturnValue(
      mockQuerySuccess({ items: [moscowFramework], total: 1 }),
    )
    const user = userEvent.setup()
    render(<PriorityOverrideForm scenarioId="scenario-1" />)

    await user.selectOptions(screen.getByLabelText('Override framework'), 'framework-2')
    expect(screen.getByLabelText('Hypothetical category')).toBeInTheDocument()
  })

  it('submits the selected project, framework, and criterion overrides', async () => {
    const mutate = vi.fn()
    mockMutation({ mutate })
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [project], total: 1 }))
    mockedUseFrameworks.mockReturnValue(
      mockQuerySuccess({ items: [riceFramework], total: 1 }),
    )
    const user = userEvent.setup()
    render(<PriorityOverrideForm scenarioId="scenario-1" />)

    await user.selectOptions(screen.getByLabelText('Project'), 'project-1')
    await user.selectOptions(screen.getByLabelText('Override framework'), 'framework-1')
    await user.type(screen.getByLabelText('Reach'), '9000')
    await user.click(screen.getByRole('button', { name: /save hypothetical values/i }))

    expect(mutate).toHaveBeenCalledWith(
      {
        project_id: 'project-1',
        framework_id: 'framework-1',
        values: [{ criterion_key: 'reach', value: '9000' }],
        category: null,
      },
      expect.anything(),
    )
  })
})

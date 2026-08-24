import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PriorityOverrideList } from './PriorityOverrideList'
import { useDeleteScenarioPriorityOverride } from '../hooks/useScenarioPriorityOverrideMutations'
import { makeScenarioPriorityOverride } from '@/test/fixtures'

vi.mock('../hooks/useScenarioPriorityOverrideMutations')

const mockedUseDeleteOverride = vi.mocked(useDeleteScenarioPriorityOverride)

function mockMutation(overrides: Record<string, unknown> = {}) {
  mockedUseDeleteOverride.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    ...overrides,
  } as unknown as ReturnType<typeof useDeleteScenarioPriorityOverride>)
}

describe('PriorityOverrideList', () => {
  it('shows an empty state when there are no overrides', () => {
    mockMutation()
    render(<PriorityOverrideList scenarioId="scenario-1" overrides={[]} />)
    expect(
      screen.getByText(/No hypothetical prioritization values recorded/),
    ).toBeInTheDocument()
  })

  it('lists a criterion-value override', () => {
    mockMutation()
    render(
      <PriorityOverrideList
        scenarioId="scenario-1"
        overrides={[makeScenarioPriorityOverride({ values: { reach: '5000' } })]}
      />,
    )
    expect(screen.getByText('Website Redesign')).toBeInTheDocument()
    expect(screen.getByText('reach=5000')).toBeInTheDocument()
  })

  it('lists a MoSCoW category override', () => {
    mockMutation()
    render(
      <PriorityOverrideList
        scenarioId="scenario-1"
        overrides={[makeScenarioPriorityOverride({ values: {}, category: 'must' })]}
      />,
    )
    expect(screen.getByText('Category: must')).toBeInTheDocument()
  })

  it('removes an override', async () => {
    const mutate = vi.fn()
    mockMutation({ mutate })
    const user = userEvent.setup()
    render(
      <PriorityOverrideList
        scenarioId="scenario-1"
        overrides={[makeScenarioPriorityOverride({ id: 'override-1' })]}
      />,
    )
    await user.click(screen.getByRole('button', { name: /remove/i }))
    expect(mutate).toHaveBeenCalledWith('override-1')
  })
})

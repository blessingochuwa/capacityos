import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FrameworkCriteriaEditor } from './FrameworkCriteriaEditor'
import { useAddCriterion, useRemoveCriterion, useUpdateCriterion } from '../hooks/useCriterionMutations'
import { makePrioritizationCriterion, makePrioritizationFramework } from '@/test/fixtures'

vi.mock('../hooks/useCriterionMutations')

const mockedUseAddCriterion = vi.mocked(useAddCriterion)
const mockedUseUpdateCriterion = vi.mocked(useUpdateCriterion)
const mockedUseRemoveCriterion = vi.mocked(useRemoveCriterion)

function mockMutations(overrides: {
  add?: Record<string, unknown>
  update?: Record<string, unknown>
  remove?: Record<string, unknown>
} = {}) {
  mockedUseAddCriterion.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.add,
  } as unknown as ReturnType<typeof useAddCriterion>)
  mockedUseUpdateCriterion.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.update,
  } as unknown as ReturnType<typeof useUpdateCriterion>)
  mockedUseRemoveCriterion.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.remove,
  } as unknown as ReturnType<typeof useRemoveCriterion>)
}

const weightedFramework = makePrioritizationFramework({
  framework_type: 'weighted',
  criteria: [
    makePrioritizationCriterion({
      id: 'c-1',
      key: 'business_value',
      name: 'Business Value',
      weight: '3.000',
      is_editable: true,
    }),
    makePrioritizationCriterion({
      id: 'c-2',
      key: 'urgency',
      name: 'Urgency',
      weight: '2.000',
      is_editable: true,
    }),
  ],
})

describe('FrameworkCriteriaEditor', () => {
  it('renders one row per existing criterion', () => {
    mockMutations()
    render(<FrameworkCriteriaEditor framework={weightedFramework} />)
    expect(screen.getByLabelText('Business Value name')).toHaveValue('Business Value')
    expect(screen.getByLabelText('Urgency name')).toHaveValue('Urgency')
  })

  it('saves a renamed and reweighted criterion', async () => {
    const mutate = vi.fn()
    mockMutations({ update: { mutate } })
    const user = userEvent.setup()
    render(<FrameworkCriteriaEditor framework={weightedFramework} />)

    const nameInput = screen.getByLabelText('Business Value name')
    await user.clear(nameInput)
    await user.type(nameInput, 'Strategic Value')
    const saveButtons = screen.getAllByRole('button', { name: /^save$/i })
    await user.click(saveButtons[0])

    expect(mutate).toHaveBeenCalledWith({
      criterionId: 'c-1',
      data: { name: 'Strategic Value', weight: '3.000' },
    })
  })

  it('adds a new criterion', async () => {
    const mutate = vi.fn()
    mockMutations({ add: { mutate } })
    const user = userEvent.setup()
    render(<FrameworkCriteriaEditor framework={weightedFramework} />)

    await user.type(screen.getByPlaceholderText('New criterion name'), 'Risk')
    await user.clear(screen.getByPlaceholderText('Weight'))
    await user.type(screen.getByPlaceholderText('Weight'), '1.5')
    await user.click(screen.getByRole('button', { name: /add criterion/i }))

    expect(mutate).toHaveBeenCalledWith(
      { name: 'Risk', weight: '1.5' },
      expect.anything(),
    )
  })

  it('removes a criterion', async () => {
    const mutate = vi.fn()
    mockMutations({ remove: { mutate } })
    const user = userEvent.setup()
    render(<FrameworkCriteriaEditor framework={weightedFramework} />)

    const removeButtons = screen.getAllByRole('button', { name: /^remove$/i })
    await user.click(removeButtons[0])

    expect(mutate).toHaveBeenCalledWith('c-1')
  })

  it('disables removal when only one criterion remains', () => {
    mockMutations()
    const singleCriterionFramework = makePrioritizationFramework({
      framework_type: 'weighted',
      criteria: [
        makePrioritizationCriterion({ id: 'c-1', key: 'value', name: 'Value', weight: '1.000' }),
      ],
    })
    render(<FrameworkCriteriaEditor framework={singleCriterionFramework} />)
    expect(screen.getByRole('button', { name: /^remove$/i })).toBeDisabled()
  })
})

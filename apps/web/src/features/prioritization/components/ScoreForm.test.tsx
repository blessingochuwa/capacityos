import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ScoreForm } from './ScoreForm'
import { useCreateScore, useUpdateScore } from '../hooks/useScoreMutations'
import { makePrioritizationFramework, makeProjectPriorityScore } from '@/test/fixtures'

vi.mock('../hooks/useScoreMutations')

const mockedUseCreateScore = vi.mocked(useCreateScore)
const mockedUseUpdateScore = vi.mocked(useUpdateScore)

function mockMutations(overrides: {
  create?: Record<string, unknown>
  update?: Record<string, unknown>
} = {}) {
  mockedUseCreateScore.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.create,
  } as unknown as ReturnType<typeof useCreateScore>)
  mockedUseUpdateScore.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.update,
  } as unknown as ReturnType<typeof useUpdateScore>)
}

describe('ScoreForm (create mode)', () => {
  it('renders one input per framework criterion', () => {
    mockMutations()
    const framework = makePrioritizationFramework()
    render(<ScoreForm projectId="project-1" framework={framework} />)
    expect(screen.getByLabelText('Reach')).toBeInTheDocument()
    expect(screen.getByLabelText('Impact')).toBeInTheDocument()
    expect(screen.getByLabelText('Confidence')).toBeInTheDocument()
    expect(screen.getByLabelText('Effort')).toBeInTheDocument()
  })

  it('submits only the criteria that were actually filled in', async () => {
    const mutate = vi.fn()
    mockMutations({ create: { mutate } })
    const framework = makePrioritizationFramework()
    const user = userEvent.setup()
    render(<ScoreForm projectId="project-1" framework={framework} />)

    await user.type(screen.getByLabelText('Reach'), '1000')
    await user.type(screen.getByLabelText('Impact'), '2')
    await user.click(screen.getByRole('button', { name: /save score/i }))

    expect(mutate).toHaveBeenCalledWith(
      {
        framework_id: framework.id,
        values: [
          { criterion_key: 'reach', value: '1000' },
          { criterion_key: 'impact', value: '2' },
        ],
        notes: undefined,
      },
      expect.anything(),
    )
  })

  it('shows the backend error message when submission fails', () => {
    mockMutations({ create: { isError: true, error: { message: 'Something went wrong.' } } })
    render(<ScoreForm projectId="project-1" framework={makePrioritizationFramework()} />)
    expect(screen.getByText('Something went wrong.')).toBeInTheDocument()
  })
})

describe('ScoreForm (edit mode)', () => {
  it('pre-fills inputs from the existing score breakdown', () => {
    mockMutations()
    const framework = makePrioritizationFramework()
    const score = makeProjectPriorityScore({
      breakdown: { reach: '1000', impact: '2', confidence: '0.8', effort: '4' },
    })
    render(<ScoreForm projectId="project-1" framework={framework} score={score} />)
    expect(screen.getByLabelText('Reach')).toHaveValue('1000')
    expect(screen.getByLabelText('Effort')).toHaveValue('4')
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })

  it('calls onCancel when Cancel is clicked', async () => {
    mockMutations()
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(
      <ScoreForm
        projectId="project-1"
        framework={makePrioritizationFramework()}
        score={makeProjectPriorityScore()}
        onCancel={onCancel}
      />,
    )
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onCancel).toHaveBeenCalled()
  })
})

describe('ScoreForm (MoSCoW framework)', () => {
  it('renders a category selector instead of criterion inputs', () => {
    mockMutations()
    const framework = makePrioritizationFramework({ framework_type: 'moscow', criteria: [] })
    render(<ScoreForm projectId="project-1" framework={framework} />)
    expect(screen.getByLabelText('Category')).toBeInTheDocument()
    expect(screen.queryByLabelText('Reach')).not.toBeInTheDocument()
  })

  it('submits the selected category and no numeric values', async () => {
    const mutate = vi.fn()
    mockMutations({ create: { mutate } })
    const framework = makePrioritizationFramework({
      id: 'framework-moscow',
      framework_type: 'moscow',
      criteria: [],
    })
    const user = userEvent.setup()
    render(<ScoreForm projectId="project-1" framework={framework} />)

    await user.selectOptions(screen.getByLabelText('Category'), 'must')
    await user.click(screen.getByRole('button', { name: /save score/i }))

    expect(mutate).toHaveBeenCalledWith(
      {
        framework_id: 'framework-moscow',
        values: [],
        category: 'must',
        notes: undefined,
      },
      expect.anything(),
    )
  })

  it('pre-fills the category when editing an existing MoSCoW score', () => {
    mockMutations()
    const framework = makePrioritizationFramework({ framework_type: 'moscow', criteria: [] })
    const score = makeProjectPriorityScore({
      framework_type: 'moscow',
      breakdown: {},
      category: 'should',
    })
    render(<ScoreForm projectId="project-1" framework={framework} score={score} />)
    expect(screen.getByLabelText('Category')).toHaveValue('should')
  })
})

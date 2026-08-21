import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StakeholderForm } from './StakeholderForm'
import { useCreateStakeholder, useUpdateStakeholder } from '../hooks/useStakeholderMutations'
import { usePeople } from '@/hooks/usePeople'
import { makeStakeholder } from '@/test/fixtures'

vi.mock('../hooks/useStakeholderMutations')
vi.mock('@/hooks/usePeople')

const mockedUseCreateStakeholder = vi.mocked(useCreateStakeholder)
const mockedUseUpdateStakeholder = vi.mocked(useUpdateStakeholder)
const mockedUsePeople = vi.mocked(usePeople)

function mockPeopleEmpty() {
  mockedUsePeople.mockReturnValue({
    data: { items: [], total: 0 },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof usePeople>)
}

function mockMutations(overrides: {
  create?: Record<string, unknown>
  update?: Record<string, unknown>
} = {}) {
  mockedUseCreateStakeholder.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.create,
  } as unknown as ReturnType<typeof useCreateStakeholder>)
  mockedUseUpdateStakeholder.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides.update,
  } as unknown as ReturnType<typeof useUpdateStakeholder>)
}

describe('StakeholderForm (create mode)', () => {
  it('disables submit until a name and role are entered', () => {
    mockPeopleEmpty()
    mockMutations()

    render(<StakeholderForm projectId="project-1" />)
    expect(screen.getByRole('button', { name: /add stakeholder/i })).toBeDisabled()
  })

  it('submits the trimmed name/role and selected influence', async () => {
    mockPeopleEmpty()
    const mutate = vi.fn()
    mockMutations({ create: { mutate } })

    const user = userEvent.setup()
    render(<StakeholderForm projectId="project-1" />)

    await user.type(screen.getByLabelText('Name'), '  Jordan Client  ')
    await user.type(screen.getByLabelText('Role'), 'Sponsor')
    await user.selectOptions(screen.getByLabelText('Influence'), 'high')
    await user.click(screen.getByRole('button', { name: /add stakeholder/i }))

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Jordan Client', role: 'Sponsor', influence: 'high' }),
      expect.anything(),
    )
  })

  it('shows the backend error message when creation fails', () => {
    mockPeopleEmpty()
    mockMutations({
      create: { isError: true, error: { message: 'Something went wrong.' } },
    })

    render(<StakeholderForm projectId="project-1" />)
    expect(screen.getByText('Something went wrong.')).toBeInTheDocument()
  })
})

describe('StakeholderForm (edit mode)', () => {
  it('pre-fills fields from the given stakeholder', () => {
    mockPeopleEmpty()
    mockMutations()
    const stakeholder = makeStakeholder({ name: 'Jordan Client', role: 'Sponsor' })

    render(<StakeholderForm projectId="project-1" stakeholder={stakeholder} />)
    expect(screen.getByLabelText('Name')).toHaveValue('Jordan Client')
    expect(screen.getByLabelText('Role')).toHaveValue('Sponsor')
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })

  it('submits only the changed fields on update', async () => {
    mockPeopleEmpty()
    const mutate = vi.fn()
    mockMutations({ update: { mutate } })
    const stakeholder = makeStakeholder({ name: 'Jordan Client', role: 'Sponsor' })

    const user = userEvent.setup()
    render(<StakeholderForm projectId="project-1" stakeholder={stakeholder} />)

    await user.clear(screen.getByLabelText('Role'))
    await user.type(screen.getByLabelText('Role'), 'Reviewer')
    await user.click(screen.getByRole('button', { name: /save changes/i }))

    expect(mutate).toHaveBeenCalledWith(
      { stakeholderId: stakeholder.id, data: { role: 'Reviewer' } },
      expect.anything(),
    )
  })

  it('calls onCancel when Cancel is clicked', async () => {
    mockPeopleEmpty()
    mockMutations()
    const onCancel = vi.fn()
    const user = userEvent.setup()

    render(
      <StakeholderForm
        projectId="project-1"
        stakeholder={makeStakeholder()}
        onCancel={onCancel}
      />,
    )
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onCancel).toHaveBeenCalled()
  })
})

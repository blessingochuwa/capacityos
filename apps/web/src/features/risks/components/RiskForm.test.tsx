import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RiskForm } from './RiskForm'
import { useCreateRisk } from '../hooks/useRiskMutations'
import { usePeople } from '@/hooks/usePeople'

vi.mock('../hooks/useRiskMutations')
vi.mock('@/hooks/usePeople')

const mockedUseCreateRisk = vi.mocked(useCreateRisk)
const mockedUsePeople = vi.mocked(usePeople)

function mockPeopleEmpty() {
  mockedUsePeople.mockReturnValue({
    data: { items: [], total: 0 },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof usePeople>)
}

describe('RiskForm', () => {
  it('disables submit until a description is entered', () => {
    mockPeopleEmpty()
    mockedUseCreateRisk.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useCreateRisk>)

    render(<RiskForm projectId="project-1" />)
    expect(screen.getByRole('button', { name: /add risk/i })).toBeDisabled()
  })

  it('submits the trimmed description and selected probability/impact', async () => {
    mockPeopleEmpty()
    const mutate = vi.fn()
    mockedUseCreateRisk.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useCreateRisk>)

    const user = userEvent.setup()
    render(<RiskForm projectId="project-1" />)

    await user.type(screen.getByLabelText('Description'), '  Vendor delay  ')
    await user.selectOptions(screen.getByLabelText('Probability'), 'high')
    await user.click(screen.getByRole('button', { name: /add risk/i }))

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({
        description: 'Vendor delay',
        probability: 'high',
        impact: 'medium',
      }),
      expect.anything(),
    )
  })

  it('shows the backend error message when creation fails', () => {
    mockPeopleEmpty()
    mockedUseCreateRisk.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: true,
      error: { message: 'A project with that risk already exists.' },
    } as unknown as ReturnType<typeof useCreateRisk>)

    render(<RiskForm projectId="project-1" />)
    expect(
      screen.getByText('A project with that risk already exists.'),
    ).toBeInTheDocument()
  })
})

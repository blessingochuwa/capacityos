import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FrameworkForm } from './FrameworkForm'
import { useCreateFramework } from '../hooks/useFrameworkMutations'

vi.mock('../hooks/useFrameworkMutations')

const mockedUseCreateFramework = vi.mocked(useCreateFramework)

function mockMutation(overrides: Record<string, unknown> = {}) {
  mockedUseCreateFramework.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...overrides,
  } as unknown as ReturnType<typeof useCreateFramework>)
}

describe('FrameworkForm', () => {
  it('disables submit until a name is entered', () => {
    mockMutation()
    render(<FrameworkForm />)
    expect(screen.getByRole('button', { name: /create framework/i })).toBeDisabled()
  })

  it('submits a RICE framework with no criteria', async () => {
    const mutate = vi.fn()
    mockMutation({ mutate })
    const user = userEvent.setup()
    render(<FrameworkForm />)

    await user.type(screen.getByLabelText('Framework name'), 'Feature RICE')
    await user.click(screen.getByRole('button', { name: /create framework/i }))

    expect(mutate).toHaveBeenCalledWith(
      { name: 'Feature RICE', framework_type: 'rice', criteria: [] },
      expect.anything(),
    )
  })

  it('requires at least one named criterion for a weighted framework', async () => {
    mockMutation()
    const user = userEvent.setup()
    render(<FrameworkForm />)

    await user.type(screen.getByLabelText('Framework name'), 'Platform Weighted')
    await user.selectOptions(screen.getByLabelText('Framework type'), 'weighted')

    expect(screen.getByRole('button', { name: /create framework/i })).toBeDisabled()
  })

  it('submits a weighted framework with its named, weighted criteria', async () => {
    const mutate = vi.fn()
    mockMutation({ mutate })
    const user = userEvent.setup()
    render(<FrameworkForm />)

    await user.type(screen.getByLabelText('Framework name'), 'Platform Weighted')
    await user.selectOptions(screen.getByLabelText('Framework type'), 'weighted')
    await user.type(
      screen.getByPlaceholderText('Criterion name (e.g. Business Value)'),
      'Business Value',
    )
    await user.clear(screen.getByPlaceholderText('Weight'))
    await user.type(screen.getByPlaceholderText('Weight'), '3')
    await user.click(screen.getByRole('button', { name: /create framework/i }))

    expect(mutate).toHaveBeenCalledWith(
      {
        name: 'Platform Weighted',
        framework_type: 'weighted',
        criteria: [{ name: 'Business Value', weight: '3' }],
      },
      expect.anything(),
    )
  })

  it('shows the backend error message when creation fails', () => {
    mockMutation({ isError: true, error: { message: 'A framework named X already exists.' } })
    render(<FrameworkForm />)
    expect(screen.getByText('A framework named X already exists.')).toBeInTheDocument()
  })

  it('submits a MoSCoW framework with no criteria at all', async () => {
    const mutate = vi.fn()
    mockMutation({ mutate })
    const user = userEvent.setup()
    render(<FrameworkForm />)

    await user.type(screen.getByLabelText('Framework name'), 'Release MoSCoW')
    await user.selectOptions(screen.getByLabelText('Framework type'), 'moscow')
    expect(
      screen.getByText(/MoSCoW has no numeric criteria at all/i),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /create framework/i }))

    expect(mutate).toHaveBeenCalledWith(
      { name: 'Release MoSCoW', framework_type: 'moscow', criteria: [] },
      expect.anything(),
    )
  })

  it('submits an ICE framework with no criteria', async () => {
    const mutate = vi.fn()
    mockMutation({ mutate })
    const user = userEvent.setup()
    render(<FrameworkForm />)

    await user.type(screen.getByLabelText('Framework name'), 'Feature ICE')
    await user.selectOptions(screen.getByLabelText('Framework type'), 'ice')
    await user.click(screen.getByRole('button', { name: /create framework/i }))

    expect(mutate).toHaveBeenCalledWith(
      { name: 'Feature ICE', framework_type: 'ice', criteria: [] },
      expect.anything(),
    )
  })
})

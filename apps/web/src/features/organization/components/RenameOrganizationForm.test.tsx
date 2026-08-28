import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RenameOrganizationForm } from './RenameOrganizationForm'

describe('RenameOrganizationForm', () => {
  it('seeds the field with the current name and disables save until it changes', async () => {
    const user = userEvent.setup()
    render(
      <RenameOrganizationForm
        currentName="Acme Corp"
        onSubmit={vi.fn()}
        isPending={false}
      />,
    )
    const input = screen.getByLabelText('Organization name')
    expect(input).toHaveValue('Acme Corp')

    const save = screen.getByRole('button', { name: 'Save name' })
    expect(save).toBeDisabled()

    await user.type(input, ' Ltd')
    expect(save).toBeEnabled()
  })

  it('stays disabled when the trimmed name is empty or unchanged', async () => {
    const user = userEvent.setup()
    render(
      <RenameOrganizationForm
        currentName="Acme Corp"
        onSubmit={vi.fn()}
        isPending={false}
      />,
    )
    const input = screen.getByLabelText('Organization name')
    const save = screen.getByRole('button', { name: 'Save name' })

    await user.clear(input)
    expect(save).toBeDisabled()

    await user.type(input, '   ')
    expect(save).toBeDisabled()

    await user.clear(input)
    await user.type(input, 'Acme Corp')
    expect(save).toBeDisabled()
  })

  it('submits the trimmed new name', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(
      <RenameOrganizationForm
        currentName="Acme Corp"
        onSubmit={onSubmit}
        isPending={false}
      />,
    )
    const input = screen.getByLabelText('Organization name')
    await user.clear(input)
    await user.type(input, '  Acme Corporation  ')
    await user.click(screen.getByRole('button', { name: 'Save name' }))

    expect(onSubmit).toHaveBeenCalledWith('Acme Corporation')
  })

  it('shows the pending label and disables save while saving', () => {
    render(
      <RenameOrganizationForm
        currentName="Acme Corp"
        onSubmit={vi.fn().mockResolvedValue(undefined)}
        isPending
      />,
    )
    expect(screen.getByRole('button', { name: 'Saving…' })).toBeDisabled()
  })

  it('renders a server error as an alert', () => {
    render(
      <RenameOrganizationForm
        currentName="Acme Corp"
        onSubmit={vi.fn()}
        isPending={false}
        error="String should have at most 200 characters"
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      'String should have at most 200 characters',
    )
  })
})

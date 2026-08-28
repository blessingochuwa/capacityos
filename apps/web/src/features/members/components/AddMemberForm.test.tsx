import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AddMemberForm } from './AddMemberForm'

describe('AddMemberForm', () => {
  it('submits the trimmed email and chosen role, then clears the field', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(<AddMemberForm onSubmit={onSubmit} isPending={false} />)

    await user.type(
      screen.getByLabelText('Email of an existing account'),
      '  grace@acme.test  ',
    )
    await user.selectOptions(screen.getByLabelText('Initial role'), 'manager')
    await user.click(screen.getByRole('button', { name: 'Add member' }))

    expect(onSubmit).toHaveBeenCalledWith('grace@acme.test', 'manager')
    await waitFor(() =>
      expect(screen.getByLabelText('Email of an existing account')).toHaveValue(''),
    )
  })

  it('keeps the email field when the submission fails', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error('User not found: grace@acme.test'))
    const user = userEvent.setup()
    render(
      <AddMemberForm
        onSubmit={onSubmit}
        isPending={false}
        error="User not found: grace@acme.test"
      />,
    )

    await user.type(
      screen.getByLabelText('Email of an existing account'),
      'grace@acme.test',
    )
    await user.click(screen.getByRole('button', { name: 'Add member' }))

    expect(onSubmit).toHaveBeenCalled()
    await waitFor(() =>
      expect(
        screen.getByLabelText('Email of an existing account'),
      ).toHaveValue('grace@acme.test'),
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      'User not found: grace@acme.test',
    )
  })

  it('disables the button while a submission is pending or the field is empty', () => {
    const { rerender } = render(
      <AddMemberForm onSubmit={vi.fn().mockResolvedValue(undefined)} isPending={false} />,
    )
    expect(screen.getByRole('button', { name: 'Add member' })).toBeDisabled()

    rerender(
      <AddMemberForm onSubmit={vi.fn().mockResolvedValue(undefined)} isPending />,
    )
    expect(screen.getByRole('button', { name: 'Adding…' })).toBeDisabled()
  })
})

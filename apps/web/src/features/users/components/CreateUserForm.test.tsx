import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CreateUserForm } from './CreateUserForm'

const PEOPLE = [
  { id: 'person-1', display_name: 'Ada Lovelace' },
  { id: 'person-2', display_name: 'Alan Turing' },
]

describe('CreateUserForm', () => {
  it('keeps submit disabled until name, email, and a 10+ char password are present', async () => {
    const user = userEvent.setup()
    render(
      <CreateUserForm eligiblePeople={PEOPLE} onSubmit={vi.fn()} isPending={false} />,
    )
    const submit = screen.getByRole('button', { name: 'Create account' })
    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText('Display name'), 'New Person')
    await user.type(screen.getByLabelText('Email'), 'new@acme.test')
    await user.type(screen.getByLabelText('Initial password'), 'short')
    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText('Initial password'), 'enough123')
    expect(submit).toBeEnabled()
  })

  it('submits trimmed values with a null person link when none is chosen, then clears', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(
      <CreateUserForm eligiblePeople={PEOPLE} onSubmit={onSubmit} isPending={false} />,
    )

    await user.type(screen.getByLabelText('Display name'), '  New Person  ')
    await user.type(screen.getByLabelText('Email'), '  new@acme.test  ')
    await user.type(screen.getByLabelText('Initial password'), 'a-good-password')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(onSubmit).toHaveBeenCalledWith({
      email: 'new@acme.test',
      password: 'a-good-password',
      display_name: 'New Person',
      person_id: null,
    })
    await waitFor(() =>
      expect(screen.getByLabelText('Email')).toHaveValue(''),
    )
  })

  it('passes the chosen person id and keeps fields on failure', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(new Error("A user with email 'new@acme.test' already exists."))
    const user = userEvent.setup()
    render(
      <CreateUserForm
        eligiblePeople={PEOPLE}
        onSubmit={onSubmit}
        isPending={false}
        error="A user with email 'new@acme.test' already exists."
      />,
    )

    await user.type(screen.getByLabelText('Display name'), 'New Person')
    await user.type(screen.getByLabelText('Email'), 'new@acme.test')
    await user.type(screen.getByLabelText('Initial password'), 'a-good-password')
    await user.selectOptions(screen.getByLabelText('Linked person (optional)'), 'person-2')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ person_id: 'person-2' }),
    )
    await waitFor(() =>
      expect(screen.getByLabelText('Email')).toHaveValue('new@acme.test'),
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      "A user with email 'new@acme.test' already exists.",
    )
  })

  it('shows the pending label and disables submit while creating', () => {
    render(
      <CreateUserForm
        eligiblePeople={PEOPLE}
        onSubmit={vi.fn().mockResolvedValue(undefined)}
        isPending
      />,
    )
    expect(screen.getByRole('button', { name: 'Creating…' })).toBeDisabled()
  })
})

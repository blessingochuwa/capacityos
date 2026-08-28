import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DeactivateOrganizationSection } from './DeactivateOrganizationSection'

describe('DeactivateOrganizationSection', () => {
  it('requires a two-step confirmation before firing onConfirm', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    render(
      <DeactivateOrganizationSection
        organizationName="Acme Corp"
        onConfirm={onConfirm}
        isPending={false}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Deactivate organization' }))
    expect(onConfirm).not.toHaveBeenCalled()
    expect(screen.getByText('Deactivate Acme Corp?')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText('Deactivate Acme Corp?')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Deactivate organization' }))
    await user.click(screen.getByRole('button', { name: 'Confirm deactivate' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('disables the confirm button and shows a pending label while the request is in flight', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    render(
      <DeactivateOrganizationSection
        organizationName="Acme Corp"
        onConfirm={onConfirm}
        isPending
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Deactivate organization' }))
    const confirm = screen.getByRole('button', { name: 'Deactivating…' })
    expect(confirm).toBeDisabled()
    await user.click(confirm)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('surfaces the backend safety-guard message verbatim without claiming success', () => {
    render(
      <DeactivateOrganizationSection
        organizationName="Acme Corp"
        onConfirm={vi.fn()}
        isPending={false}
        error="This organization cannot be deactivated while it has only one active Owner — deactivation would leave no one able to reactivate it. Add a second Owner first, then try again."
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      'This organization cannot be deactivated while it has only one active Owner',
    )
  })
})

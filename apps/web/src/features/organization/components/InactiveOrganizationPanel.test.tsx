import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { InactiveOrganizationPanel } from './InactiveOrganizationPanel'

describe('InactiveOrganizationPanel', () => {
  it('names the inactive organization and explains recovery', () => {
    render(
      <InactiveOrganizationPanel
        organizationName="Acme Corp"
        onReactivate={vi.fn()}
        isPending={false}
      />,
    )
    expect(screen.getByText('This organization is inactive')).toBeInTheDocument()
    expect(screen.getByText('Acme Corp has been deactivated.')).toBeInTheDocument()
    expect(screen.getByText(/You will not need to sign in again/)).toBeInTheDocument()
  })

  it('calls onReactivate when the button is clicked', async () => {
    const onReactivate = vi.fn()
    const user = userEvent.setup()
    render(
      <InactiveOrganizationPanel
        organizationName="Acme Corp"
        onReactivate={onReactivate}
        isPending={false}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Reactivate organization' }))
    expect(onReactivate).toHaveBeenCalledTimes(1)
  })

  it('shows a pending label and blocks repeat clicks while reactivating', async () => {
    const onReactivate = vi.fn()
    const user = userEvent.setup()
    render(
      <InactiveOrganizationPanel
        organizationName="Acme Corp"
        onReactivate={onReactivate}
        isPending
      />,
    )
    const button = screen.getByRole('button', { name: 'Reactivating…' })
    expect(button).toBeDisabled()
    await user.click(button)
    expect(onReactivate).not.toHaveBeenCalled()
  })

  it('surfaces a backend error verbatim', () => {
    render(
      <InactiveOrganizationPanel
        organizationName="Acme Corp"
        onReactivate={vi.fn()}
        isPending={false}
        error="Only an Owner can reactivate an organization."
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Only an Owner can reactivate an organization.',
    )
  })
})

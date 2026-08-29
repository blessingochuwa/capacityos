import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UsersFilterBar } from './UsersFilterBar'

describe('UsersFilterBar', () => {
  it('reports search box input to the caller', async () => {
    const onSearchChange = vi.fn()
    const user = userEvent.setup()
    render(
      <UsersFilterBar
        searchValue=""
        onSearchChange={onSearchChange}
        statusValue=""
        onStatusChange={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('Search'), 'a')
    expect(onSearchChange).toHaveBeenCalledWith('a')
  })

  it('offers Active/Invited/Disabled as status options and reports a change', async () => {
    const onStatusChange = vi.fn()
    const user = userEvent.setup()
    render(
      <UsersFilterBar
        searchValue=""
        onSearchChange={vi.fn()}
        statusValue=""
        onStatusChange={onStatusChange}
      />,
    )

    const select = screen.getByLabelText('Status')
    expect(select).toHaveTextContent('Active')
    expect(select).toHaveTextContent('Invited')
    expect(select).toHaveTextContent('Disabled')

    await user.selectOptions(select, 'disabled')
    expect(onStatusChange).toHaveBeenCalledWith('disabled')
  })

  it('reflects the controlled search and status values', () => {
    render(
      <UsersFilterBar
        searchValue="grace"
        onSearchChange={vi.fn()}
        statusValue="invited"
        onStatusChange={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Search')).toHaveValue('grace')
    expect(screen.getByLabelText('Status')).toHaveValue('invited')
  })
})

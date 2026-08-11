import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DateRangeControl } from './DateRangeControl'
import { thisMonth, thisWeek } from '../utils/dateRange'

describe('DateRangeControl', () => {
  it('highlights the preset matching the current range', () => {
    render(<DateRangeControl range={thisWeek()} onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'This week' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: 'This month' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('calling a preset resolves and reports the concrete range', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<DateRangeControl range={thisWeek()} onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: 'This month' }))

    expect(onChange).toHaveBeenCalledWith(thisMonth())
  })

  it('shows "Custom range" once the range no longer matches any preset', () => {
    render(
      <DateRangeControl
        range={{ start: '2020-01-01', end: '2020-01-05' }}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText('Custom range')).toBeInTheDocument()
  })

  it('editing the start date field reports the updated range', () => {
    const onChange = vi.fn()
    const range = thisWeek()
    render(<DateRangeControl range={range} onChange={onChange} />)

    const startInput = screen.getByLabelText('Start date')
    fireEvent.change(startInput, { target: { value: '2026-08-18' } })

    expect(onChange).toHaveBeenCalledWith({
      start: '2026-08-18',
      end: range.end,
    })
  })
})

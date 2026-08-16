import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SignalList } from './SignalList'
import { signalKey } from '../utils/presentation'
import { makeSignal } from '@/test/fixtures'

describe('SignalList', () => {
  it('renders a reassuring healthy empty state, not a generic "no data" message', () => {
    render(<SignalList signals={[]} />)
    expect(
      screen.getByText('No signals — this team is healthy for this period.'),
    ).toBeInTheDocument()
  })

  it('renders each signal with its severity and explanation', () => {
    const signal = makeSignal({ entity_label: 'Jane Doe' })
    render(<SignalList signals={[signal]} />)
    expect(screen.getByText('Critical')).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.getByText(signal.explanation)).toBeInTheDocument()
  })

  it('marks the selected row and calls onSelect with its key', async () => {
    const user = userEvent.setup()
    const signal = makeSignal()
    const onSelect = vi.fn()
    render(
      <SignalList
        signals={[signal]}
        selectedKey={signalKey(signal)}
        onSelect={onSelect}
      />,
    )

    const row = screen.getByRole('button', { pressed: true })
    expect(row).toBeInTheDocument()

    await user.click(row)
    expect(onSelect).toHaveBeenCalledWith(signalKey(signal))
  })
})

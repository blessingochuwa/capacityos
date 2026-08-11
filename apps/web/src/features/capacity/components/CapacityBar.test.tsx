import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CapacityBar } from './CapacityBar'

describe('CapacityBar', () => {
  it('describes remaining capacity when under capacity', () => {
    render(
      <CapacityBar
        effectiveCapacity="40.00"
        allocatedCapacity="32.00"
        remainingCapacity="8.00"
        overAllocation="0.00"
      />,
    )
    expect(
      screen.getByRole('img', { name: '32h of 40h allocated, 8h remaining' }),
    ).toBeInTheDocument()
  })

  it('describes the overflow — never clips — when over capacity', () => {
    render(
      <CapacityBar
        effectiveCapacity="32.00"
        allocatedCapacity="40.00"
        remainingCapacity="-8.00"
        overAllocation="8.00"
      />,
    )
    expect(
      screen.getByRole('img', {
        name: '40h of 32h allocated, 8h over capacity',
      }),
    ).toBeInTheDocument()
  })

  it('reports no effective capacity distinctly from zero utilization', () => {
    render(
      <CapacityBar
        effectiveCapacity="0.00"
        allocatedCapacity="0.00"
        remainingCapacity="0.00"
        overAllocation="0.00"
      />,
    )
    expect(
      screen.getByRole('img', { name: 'No effective capacity in this period' }),
    ).toBeInTheDocument()
  })
})

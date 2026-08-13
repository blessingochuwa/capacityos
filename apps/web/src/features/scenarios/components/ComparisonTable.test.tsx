import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ComparisonTable } from './ComparisonTable'
import { makeAggregateComparison } from '@/test/fixtures'

describe('ComparisonTable', () => {
  it('renders baseline, scenario, and change columns for every metric', () => {
    const aggregate = makeAggregateComparison()
    render(<ComparisonTable aggregate={aggregate} />)

    expect(screen.getByText('Utilization')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('+25pp')).toBeInTheDocument()

    expect(screen.getByText('Remaining capacity')).toBeInTheDocument()
    expect(screen.getByText('-10h')).toBeInTheDocument()

    expect(screen.getByText('Over-allocated people')).toBeInTheDocument()
  })
})

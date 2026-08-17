import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AiConfidenceBadge } from './AiConfidenceBadge'

describe('AiConfidenceBadge', () => {
  it('renders a category label, never a numeric probability', () => {
    render(<AiConfidenceBadge confidence="high" />)
    expect(screen.getByText('High confidence')).toBeInTheDocument()
  })

  it('renders medium and low confidence labels distinctly', () => {
    const { rerender } = render(<AiConfidenceBadge confidence="medium" />)
    expect(screen.getByText('Medium confidence')).toBeInTheDocument()
    rerender(<AiConfidenceBadge confidence="low" />)
    expect(screen.getByText('Low confidence')).toBeInTheDocument()
  })
})

import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AiResultPanel } from './AiResultPanel'
import { makeAIInsightResponse, makeAIResponseEnvelope } from '@/test/fixtures'

describe('AiResultPanel', () => {
  it('renders a loading skeleton while pending', () => {
    render(
      <AiResultPanel
        title="AI summary"
        envelope={undefined}
        isPending={true}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    )
    expect(screen.getByText('AI summary')).toBeInTheDocument()
  })

  it('renders nothing (no panel) before the first trigger', () => {
    const { container } = render(
      <AiResultPanel
        title="AI summary"
        envelope={undefined}
        isPending={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('shows ErrorState on a real transport/HTTP failure, with a retry action', () => {
    const onRetry = vi.fn()
    render(
      <AiResultPanel
        title="AI summary"
        envelope={undefined}
        isPending={false}
        isError={true}
        error={new Error('network down')}
        onRetry={onRetry}
      />,
    )
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('shows the backend unavailable message as a first-class state, not an error', () => {
    render(
      <AiResultPanel
        title="AI summary"
        envelope={makeAIResponseEnvelope({
          status: 'unavailable',
          response: null,
          message: 'AI is not configured for this deployment.',
        })}
        isPending={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    )
    expect(
      screen.getByText('AI is not configured for this deployment.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a retry action when the provider failed at request time', () => {
    render(
      <AiResultPanel
        title="AI summary"
        envelope={makeAIResponseEnvelope({
          status: 'error',
          response: null,
          message: 'The AI provider timed out. Please try again.',
        })}
        isPending={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    )
    expect(
      screen.getByText('The AI provider timed out. Please try again.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('renders summary, findings, risks, recommendations, and confidence for a successful response', () => {
    const envelope = makeAIResponseEnvelope({
      response: makeAIInsightResponse({
        summary: 'Two people are over-allocated next week.',
        key_findings: [
          { text: 'Finding one.', source_references: [] },
        ],
        risks: [{ text: 'Risk one.', source_references: [] }],
        recommendations: [
          {
            recommendation: 'Consider reviewing the shift.',
            rationale: 'Because of the evidence.',
            source_references: [],
            assumptions: [],
          },
        ],
        confidence: 'medium',
      }),
    })
    render(
      <AiResultPanel
        title="AI summary"
        envelope={envelope}
        isPending={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    )
    expect(
      screen.getByText('Two people are over-allocated next week.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Finding one.')).toBeInTheDocument()
    expect(screen.getByText('Risk one.')).toBeInTheDocument()
    expect(screen.getByText('Consider reviewing the shift.')).toBeInTheDocument()
    expect(screen.getByText('Medium confidence')).toBeInTheDocument()
  })

  it('never renders a recommendation as an executable action — no buttons besides retry appear', () => {
    const envelope = makeAIResponseEnvelope({
      response: makeAIInsightResponse({
        recommendations: [
          {
            recommendation: 'Consider shifting hours to Person B.',
            rationale: 'r',
            source_references: [],
            assumptions: [],
          },
        ],
      }),
    })
    render(
      <AiResultPanel
        title="AI summary"
        envelope={envelope}
        isPending={false}
        isError={false}
        error={null}
        onRetry={vi.fn()}
      />,
    )
    expect(screen.queryAllByRole('button')).toHaveLength(0)
  })
})

import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SummarizeButton } from './SummarizeButton'
import { useAiSummary } from '../hooks/useAiSummary'
import { makeAIResponseEnvelope } from '@/test/fixtures'

vi.mock('../hooks/useAiSummary')

const mockedUseAiSummary = vi.mocked(useAiSummary)

describe('SummarizeButton', () => {
  it('does not call the API until the button is clicked', () => {
    const mutate = vi.fn()
    mockedUseAiSummary.mockReturnValue({
      mutate,
      data: undefined,
      isPending: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useAiSummary>)

    render(
      <SummarizeButton
        entityType="team"
        entityId="team-1"
        startDate="2026-08-17"
        endDate="2026-08-21"
      />,
    )
    expect(mutate).not.toHaveBeenCalled()
    expect(screen.queryByText('AI summary')).not.toBeInTheDocument()
  })

  it('triggers a summary request with the given scope and date range on click', async () => {
    const user = userEvent.setup()
    const mutate = vi.fn()
    mockedUseAiSummary.mockReturnValue({
      mutate,
      data: undefined,
      isPending: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useAiSummary>)

    render(
      <SummarizeButton
        entityType="person"
        entityId="person-1"
        startDate="2026-08-17"
        endDate="2026-08-21"
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Summarize with AI' }))

    expect(mutate).toHaveBeenCalledWith({
      scope: { entity_type: 'person', entity_id: 'person-1' },
      start_date: '2026-08-17',
      end_date: '2026-08-21',
    })
  })

  it('renders the result panel once triggered and data has arrived', async () => {
    const user = userEvent.setup()
    mockedUseAiSummary.mockReturnValue({
      mutate: vi.fn(),
      data: undefined,
      isPending: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useAiSummary>)

    const { rerender } = render(
      <SummarizeButton
        entityType="team"
        entityId="team-1"
        startDate="2026-08-17"
        endDate="2026-08-21"
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Summarize with AI' }))

    mockedUseAiSummary.mockReturnValue({
      mutate: vi.fn(),
      data: makeAIResponseEnvelope(),
      isPending: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useAiSummary>)
    rerender(
      <SummarizeButton
        entityType="team"
        entityId="team-1"
        startDate="2026-08-17"
        endDate="2026-08-21"
      />,
    )

    expect(
      screen.getByText('No material capacity risk is currently detected for this scope.'),
    ).toBeInTheDocument()
  })
})

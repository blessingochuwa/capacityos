import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useProjects } from '@/hooks/useProjects'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import { OrgStakeholderFilterBar } from './OrgStakeholderFilterBar'

vi.mock('@/hooks/useProjects', () => ({ useProjects: vi.fn() }))

const mockedUseProjects = vi.mocked(useProjects)

function defaultProps() {
  return {
    projectId: undefined as string | undefined,
    onProjectChange: vi.fn(),
    influenceValue: '' as const,
    onInfluenceChange: vi.fn(),
    interestValue: '' as const,
    onInterestChange: vi.fn(),
    decisionAuthorityValue: '' as const,
    onDecisionAuthorityChange: vi.fn(),
  }
}

describe('OrgStakeholderFilterBar', () => {
  it('renders project, influence, interest, and decision authority controls', () => {
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    render(<OrgStakeholderFilterBar {...defaultProps()} />)

    expect(screen.getByLabelText('Project')).toBeInTheDocument()
    expect(screen.getByLabelText('Influence')).toBeInTheDocument()
    expect(screen.getByLabelText('Interest')).toBeInTheDocument()
    expect(screen.getByLabelText('Decision authority')).toBeInTheDocument()
  })

  it('offers exactly the backend vocabularies, with readable labels', () => {
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    render(<OrgStakeholderFilterBar {...defaultProps()} />)

    for (const label of ['Influence', 'Interest']) {
      const select = screen.getByLabelText(label)
      expect(select).toHaveTextContent('Low')
      expect(select).toHaveTextContent('Medium')
      expect(select).toHaveTextContent('High')
    }
    const authority = screen.getByLabelText('Decision authority')
    expect(authority).toHaveTextContent('Decision maker')
    expect(authority).toHaveTextContent('Advisor')
    expect(authority).toHaveTextContent('Informed only')
  })

  it('reports each selection through its own callback', async () => {
    mockedUseProjects.mockReturnValue(
      mockQuerySuccess({ items: [{ id: 'project-1', name: 'Website Redesign' } as never], total: 1 }),
    )
    const props = defaultProps()
    const user = userEvent.setup()
    render(<OrgStakeholderFilterBar {...props} />)

    await user.selectOptions(screen.getByLabelText('Project'), 'project-1')
    await user.selectOptions(screen.getByLabelText('Influence'), 'high')
    await user.selectOptions(screen.getByLabelText('Interest'), 'low')
    await user.selectOptions(screen.getByLabelText('Decision authority'), 'advisor')

    expect(props.onProjectChange).toHaveBeenCalledWith('project-1')
    expect(props.onInfluenceChange).toHaveBeenCalledWith('high')
    expect(props.onInterestChange).toHaveBeenCalledWith('low')
    expect(props.onDecisionAuthorityChange).toHaveBeenCalledWith('advisor')
  })
})

import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useProjects } from '@/hooks/useProjects'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import { OrgRiskFilterBar } from './OrgRiskFilterBar'

vi.mock('@/hooks/useProjects', () => ({ useProjects: vi.fn() }))

const mockedUseProjects = vi.mocked(useProjects)

function defaultProps() {
  return {
    projectId: undefined as string | undefined,
    onProjectChange: vi.fn(),
    statusValue: '' as const,
    onStatusChange: vi.fn(),
    exposureValue: '' as const,
    onExposureChange: vi.fn(),
  }
}

describe('OrgRiskFilterBar', () => {
  it('renders project, status, and exposure controls', () => {
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    render(<OrgRiskFilterBar {...defaultProps()} />)

    expect(screen.getByLabelText('Project')).toBeInTheDocument()
    expect(screen.getByLabelText('Status')).toBeInTheDocument()
    expect(screen.getByLabelText('Exposure')).toBeInTheDocument()
  })

  it('lists every status and exposure option', () => {
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    render(<OrgRiskFilterBar {...defaultProps()} />)

    const status = screen.getByLabelText('Status')
    expect(status).toHaveTextContent('Open')
    expect(status).toHaveTextContent('Mitigating')
    expect(status).toHaveTextContent('Monitoring')
    expect(status).toHaveTextContent('Closed')

    const exposure = screen.getByLabelText('Exposure')
    expect(exposure).toHaveTextContent('Low')
    expect(exposure).toHaveTextContent('Medium')
    expect(exposure).toHaveTextContent('High')
  })

  it('calls onStatusChange when a status is selected', async () => {
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    const onStatusChange = vi.fn()
    const user = userEvent.setup()
    render(<OrgRiskFilterBar {...defaultProps()} onStatusChange={onStatusChange} />)

    await user.selectOptions(screen.getByLabelText('Status'), 'open')
    expect(onStatusChange).toHaveBeenCalledWith('open')
  })

  it('calls onExposureChange when an exposure level is selected', async () => {
    mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
    const onExposureChange = vi.fn()
    const user = userEvent.setup()
    render(<OrgRiskFilterBar {...defaultProps()} onExposureChange={onExposureChange} />)

    await user.selectOptions(screen.getByLabelText('Exposure'), 'high')
    expect(onExposureChange).toHaveBeenCalledWith('high')
  })

  it('calls onProjectChange when a project is selected', async () => {
    mockedUseProjects.mockReturnValue(
      mockQuerySuccess({
        items: [{ id: 'project-1', name: 'Website Redesign' } as never],
        total: 1,
      }),
    )
    const onProjectChange = vi.fn()
    const user = userEvent.setup()
    render(<OrgRiskFilterBar {...defaultProps()} onProjectChange={onProjectChange} />)

    await user.selectOptions(screen.getByLabelText('Project'), 'project-1')
    expect(onProjectChange).toHaveBeenCalledWith('project-1')
  })
})

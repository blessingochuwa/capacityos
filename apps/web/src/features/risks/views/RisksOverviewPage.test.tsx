import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { useAuth } from '@/features/auth/context/AuthContext'
import { useProjects, useProjectsLookup } from '@/hooks/useProjects'
import { usePeopleLookup } from '@/hooks/usePeople'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import { makeProjectRisk } from '@/test/fixtures'
import type { CurrentUser } from '@/features/auth/types/auth'
import { RisksOverviewPage } from './RisksOverviewPage'
import { useDeleteRisk, useUpdateRisk } from '../hooks/useRiskMutations'
import { useOrgRisks } from '../hooks/useOrgRisks'
import { useRisks } from '../hooks/useRisks'

vi.mock('@/features/auth/context/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('@/hooks/useProjects')
vi.mock('@/hooks/usePeople', () => ({ usePeopleLookup: vi.fn() }))
vi.mock('../hooks/useRisks')
vi.mock('../hooks/useOrgRisks')
vi.mock('../hooks/useRiskMutations')

const mockedUseAuth = vi.mocked(useAuth)
const mockedUseProjects = vi.mocked(useProjects)
const mockedUseProjectsLookup = vi.mocked(useProjectsLookup)
const mockedUsePeopleLookup = vi.mocked(usePeopleLookup)
const mockedUseRisks = vi.mocked(useRisks)
const mockedUseOrgRisks = vi.mocked(useOrgRisks)
const mockedUseUpdateRisk = vi.mocked(useUpdateRisk)
const mockedUseDeleteRisk = vi.mocked(useDeleteRisk)

function authValue(overrides: Partial<ReturnType<typeof useAuth>> = {}): ReturnType<
  typeof useAuth
> {
  return {
    user: { active_organization: { id: 'org-1', name: 'Acme', slug: 'acme', is_active: true } } as CurrentUser,
    status: 'authenticated',
    can: () => true,
    canManageResource: () => true,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganization: vi.fn(),
    ...overrides,
  }
}

const IDLE_MUTATION = {
  mutate: vi.fn(),
  mutateAsync: vi.fn().mockResolvedValue(undefined),
  isPending: false,
  isError: false,
  error: null,
  variables: undefined,
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/risks']}>
      <RisksOverviewPage />
    </MemoryRouter>,
  )
}

function mockCommonHooks() {
  mockedUseAuth.mockReturnValue(authValue())
  mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
  mockedUseProjectsLookup.mockReturnValue(new Map())
  mockedUsePeopleLookup.mockReturnValue(new Map())
  mockedUseRisks.mockReturnValue(mockQuerySuccess([]))
  mockedUseUpdateRisk.mockReturnValue({ ...IDLE_MUTATION } as unknown as ReturnType<
    typeof useUpdateRisk
  >)
  mockedUseDeleteRisk.mockReturnValue({ ...IDLE_MUTATION } as unknown as ReturnType<
    typeof useDeleteRisk
  >)
}

describe('RisksOverviewPage — organization-wide register (Phase 47)', () => {
  it('renders the org-wide register card with its filters', () => {
    mockCommonHooks()
    mockedUseOrgRisks.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    renderPage()

    expect(screen.getByText('Organization-wide risk register')).toBeInTheDocument()
    expect(screen.getByLabelText('Project')).toBeInTheDocument()
    expect(screen.getByLabelText('Status')).toBeInTheDocument()
    expect(screen.getByLabelText('Exposure')).toBeInTheDocument()
  })

  it('lists risks across multiple projects using the project name lookup', () => {
    mockCommonHooks()
    mockedUseProjectsLookup.mockReturnValue(
      new Map([
        ['p1', { id: 'p1', name: 'Project A' } as never],
        ['p2', { id: 'p2', name: 'Project B' } as never],
      ]),
    )
    mockedUseOrgRisks.mockReturnValue(
      mockQuerySuccess({
        items: [
          makeProjectRisk({ id: 'r1', project_id: 'p1', description: 'Risk on A' }),
          makeProjectRisk({ id: 'r2', project_id: 'p2', description: 'Risk on B' }),
        ],
        total: 2,
      }),
    )

    renderPage()

    expect(screen.getByText('Project A')).toBeInTheDocument()
    expect(screen.getByText('Project B')).toBeInTheDocument()
  })

  it('shows the unfiltered empty state when the organization has no risks', () => {
    mockCommonHooks()
    mockedUseOrgRisks.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    renderPage()

    expect(screen.getByText('No risks recorded in this organization yet.')).toBeInTheDocument()
  })

  it('selecting a status filter resets pagination and requests the filtered set', async () => {
    mockCommonHooks()
    mockedUseOrgRisks.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    const user = userEvent.setup()
    renderPage()

    await user.selectOptions(screen.getByLabelText('Status'), 'open')

    expect(mockedUseOrgRisks).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: 'open', offset: 0 }),
    )
  })

  it('selecting an exposure filter requests the filtered set', async () => {
    mockCommonHooks()
    mockedUseOrgRisks.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    const user = userEvent.setup()
    renderPage()

    await user.selectOptions(screen.getByLabelText('Exposure'), 'high')

    expect(mockedUseOrgRisks).toHaveBeenLastCalledWith(
      expect.objectContaining({ exposure: 'high', offset: 0 }),
    )
  })

  it('shows the filtered-empty state, not the "no history" state, once a filter is applied', async () => {
    mockCommonHooks()
    mockedUseOrgRisks.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))

    const user = userEvent.setup()
    renderPage()

    await user.selectOptions(screen.getByLabelText('Status'), 'closed')

    expect(screen.getByText('No risks match these filters.')).toBeInTheDocument()
  })

  it('does not paginate when every risk fits on one page', () => {
    mockCommonHooks()
    mockedUseOrgRisks.mockReturnValue(
      mockQuerySuccess({ items: [makeProjectRisk()], total: 1 }),
    )

    renderPage()

    expect(screen.getByText('Showing 1–1 of 1 risk')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('advances to the next page and requests the next offset', async () => {
    mockCommonHooks()
    mockedUseOrgRisks.mockReturnValue(
      mockQuerySuccess({
        items: Array.from({ length: 50 }, (_, i) => makeProjectRisk({ id: `r${i}` })),
        total: 75,
      }),
    )

    const user = userEvent.setup()
    renderPage()

    expect(screen.getByText('Showing 1–50 of 75 risks')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(mockedUseOrgRisks).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 50 }))
  })
})

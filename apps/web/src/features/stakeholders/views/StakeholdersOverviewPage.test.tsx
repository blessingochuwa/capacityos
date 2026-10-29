import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { useAuth } from '@/features/auth/context/AuthContext'
import { useProjects, useProjectsLookup } from '@/hooks/useProjects'
import { usePeople, usePeopleLookup } from '@/hooks/usePeople'
import {
  mockQueryError,
  mockQueryPending,
  mockQuerySuccess,
} from '@/test/mockQueryResult'
import { makeStakeholder } from '@/test/fixtures'
import type { CurrentUser } from '@/features/auth/types/auth'
import { StakeholdersOverviewPage } from './StakeholdersOverviewPage'
import {
  useCreateStakeholder,
  useDeleteStakeholder,
  useUpdateStakeholder,
} from '../hooks/useStakeholderMutations'
import { useOrgStakeholders } from '../hooks/useOrgStakeholders'
import { useStakeholders } from '../hooks/useStakeholders'

vi.mock('@/features/auth/context/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('@/hooks/useProjects')
vi.mock('@/hooks/usePeople', () => ({
  usePeopleLookup: vi.fn(),
  usePeople: vi.fn(),
}))
vi.mock('../hooks/useStakeholders')
vi.mock('../hooks/useOrgStakeholders')
vi.mock('../hooks/useStakeholderMutations')

const mockedUseAuth = vi.mocked(useAuth)
const mockedUseProjects = vi.mocked(useProjects)
const mockedUseProjectsLookup = vi.mocked(useProjectsLookup)
const mockedUsePeopleLookup = vi.mocked(usePeopleLookup)
const mockedUseStakeholders = vi.mocked(useStakeholders)
const mockedUseOrgStakeholders = vi.mocked(useOrgStakeholders)

function authValue(canWrite = true): ReturnType<typeof useAuth> {
  return {
    user: {
      active_organization: {
        id: 'org-1',
        name: 'Acme',
        slug: 'acme',
        is_active: true,
      },
    } as CurrentUser,
    status: 'authenticated',
    can: (permission: string) => canWrite || !permission.endsWith('.write'),
    canManageResource: () => canWrite,
    login: vi.fn(),
    logout: vi.fn(),
    switchOrganization: vi.fn(),
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

function renderPage(path = '/stakeholders') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <StakeholdersOverviewPage />
    </MemoryRouter>,
  )
}

function lastOrgFilters() {
  return mockedUseOrgStakeholders.mock.lastCall?.[0]
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedUseAuth.mockReturnValue(authValue())
  mockedUseProjects.mockReturnValue(
    mockQuerySuccess({
      items: [
        { id: 'p1', name: 'Project A' } as never,
        { id: 'p2', name: 'Project B' } as never,
      ],
      total: 2,
    }),
  )
  mockedUseProjectsLookup.mockReturnValue(
    new Map([
      ['p1', { id: 'p1', name: 'Project A' } as never],
      ['p2', { id: 'p2', name: 'Project B' } as never],
    ]),
  )
  mockedUsePeopleLookup.mockReturnValue(new Map())
  vi.mocked(usePeople).mockReturnValue(
    mockQuerySuccess({ items: [], total: 0 }),
  )
  mockedUseStakeholders.mockReturnValue(mockQuerySuccess([]))
  for (const hook of [
    useCreateStakeholder,
    useUpdateStakeholder,
    useDeleteStakeholder,
  ]) {
    vi.mocked(hook).mockReturnValue({ ...IDLE_MUTATION } as never)
  }
  mockedUseOrgStakeholders.mockReturnValue(
    mockQuerySuccess({ items: [], total: 0 }),
  )
})

describe('StakeholdersOverviewPage — organization-wide register (Phase 48)', () => {
  it('renders the register card with all four filters', () => {
    renderPage()

    expect(
      screen.getByText('Organization-wide stakeholder register'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Influence')).toBeInTheDocument()
    expect(screen.getByLabelText('Interest')).toBeInTheDocument()
    expect(screen.getByLabelText('Decision authority')).toBeInTheDocument()
  })

  it('gives each register its own labelled project picker (no shared element id)', () => {
    renderPage()

    const pickers = screen.getAllByLabelText('Project')
    expect(pickers).toHaveLength(2)
    expect(pickers[0]).not.toBe(pickers[1])
    expect(pickers[1]).toHaveAttribute('id', 'org-stakeholder-project')
  })

  it('requests the unfiltered first page on load', () => {
    renderPage()

    expect(lastOrgFilters()).toEqual({
      project_id: undefined,
      influence: undefined,
      interest: undefined,
      decision_authority: undefined,
      offset: 0,
    })
  })

  it('lists stakeholders across projects with their project names', () => {
    mockedUseOrgStakeholders.mockReturnValue(
      mockQuerySuccess({
        items: [
          makeStakeholder({ id: 's1', project_id: 'p1', name: 'Ada' }),
          makeStakeholder({ id: 's2', project_id: 'p2', name: 'Bo' }),
        ],
        total: 2,
      }),
    )

    renderPage()

    const table = screen.getByRole('table', {
      name: 'Every stakeholder across every project in this organization',
    })
    expect(within(table).getByText('Project A')).toBeInTheDocument()
    expect(within(table).getByText('Project B')).toBeInTheDocument()
    expect(
      screen.getByText('Showing 1–2 of 2 stakeholders'),
    ).toBeInTheDocument()
  })

  it('combines every filter into one request', async () => {
    const user = userEvent.setup()
    renderPage()

    const projectPickers = screen.getAllByLabelText('Project')
    await user.selectOptions(projectPickers[projectPickers.length - 1], 'p2')
    await user.selectOptions(screen.getByLabelText('Influence'), 'high')
    await user.selectOptions(screen.getByLabelText('Interest'), 'medium')
    await user.selectOptions(
      screen.getByLabelText('Decision authority'),
      'decision_maker',
    )

    expect(lastOrgFilters()).toEqual({
      project_id: 'p2',
      influence: 'high',
      interest: 'medium',
      decision_authority: 'decision_maker',
      offset: 0,
    })
  })

  it.each([
    ['Influence', 'low'],
    ['Interest', 'high'],
    ['Decision authority', 'advisor'],
  ])(
    'changing %s after paging returns to the first page',
    async (label, value) => {
      mockedUseOrgStakeholders.mockReturnValue(
        mockQuerySuccess({
          items: Array.from({ length: 50 }, (_, i) =>
            makeStakeholder({ id: `s${i}` }),
          ),
          total: 120,
        }),
      )
      const user = userEvent.setup()
      renderPage()

      await user.click(screen.getByRole('button', { name: 'Next' }))
      expect(lastOrgFilters()?.offset).toBe(50)

      await user.selectOptions(screen.getByLabelText(label), value)
      expect(lastOrgFilters()?.offset).toBe(0)
    },
  )

  it('pages forward and back across boundaries and disables at each end', async () => {
    const pageOf = (count: number) =>
      mockQuerySuccess({
        items: Array.from({ length: count }, (_, i) =>
          makeStakeholder({ id: `s${i}` }),
        ),
        total: 120,
      })
    mockedUseOrgStakeholders.mockImplementation((filters) =>
      pageOf((filters?.offset ?? 0) >= 100 ? 20 : 50),
    )
    const user = userEvent.setup()
    renderPage()

    expect(
      screen.getByText('Showing 1–50 of 120 stakeholders'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(lastOrgFilters()?.offset).toBe(100)
    expect(
      screen.getByText('Showing 101–120 of 120 stakeholders'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Previous' }))
    expect(lastOrgFilters()?.offset).toBe(50)
  })

  it('shows no pagination controls when the organization has no stakeholders', () => {
    renderPage()

    expect(
      screen.getByText('No stakeholders recorded in this organization yet.'),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Next' }),
    ).not.toBeInTheDocument()
  })

  it('distinguishes a filtered no-match from an empty organization', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.selectOptions(screen.getByLabelText('Influence'), 'high')

    expect(
      screen.getByText('No stakeholders match these filters.'),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('No stakeholders recorded in this organization yet.'),
    ).not.toBeInTheDocument()
  })

  it('shows a loading state while the register loads', () => {
    mockedUseOrgStakeholders.mockReturnValue(mockQueryPending())
    renderPage()

    expect(
      screen.getByText("Loading the organization's stakeholders…"),
    ).toBeInTheDocument()
  })

  it('shows an error state with a working retry', async () => {
    const query = mockQueryError<never>(new Error('Request failed'))
    mockedUseOrgStakeholders.mockReturnValue(query)
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /retry|try again/i }))
    expect(query.refetch).toHaveBeenCalled()
  })

  it('renders the register read-only for a role without stakeholder.write', () => {
    mockedUseAuth.mockReturnValue(authValue(false))
    mockedUseOrgStakeholders.mockReturnValue(
      mockQuerySuccess({
        items: [makeStakeholder({ project_id: 'p1' })],
        total: 1,
      }),
    )
    renderPage()

    const table = screen.getByRole('table', {
      name: 'Every stakeholder across every project in this organization',
    })
    expect(within(table).queryByRole('button')).not.toBeInTheDocument()
  })
})

describe('StakeholdersOverviewPage — per-project register (regression)', () => {
  it('still asks for a project before showing a per-project register', () => {
    renderPage()

    expect(
      screen.getByText('Select a project to view or record its stakeholders.'),
    ).toBeInTheDocument()
    expect(mockedUseStakeholders).toHaveBeenLastCalledWith(undefined)
  })

  it('still loads the selected project from the URL, with edit controls', () => {
    mockedUseStakeholders.mockReturnValue(
      mockQuerySuccess([
        makeStakeholder({ id: 's1', name: 'Per-project person' }),
      ]),
    )
    renderPage('/stakeholders?project=p1')

    expect(mockedUseStakeholders).toHaveBeenLastCalledWith('p1')
    const table = screen.getByRole('table', {
      name: /Stakeholders recorded for this project/,
    })
    expect(within(table).getByText('Per-project person')).toBeInTheDocument()
    expect(
      within(table).getByRole('button', { name: 'Edit' }),
    ).toBeInTheDocument()
  })

  it('form and register controls never share an element id', () => {
    renderPage('/stakeholders?project=p1')

    for (const label of ['Influence', 'Interest', 'Decision authority']) {
      const controls = screen.getAllByLabelText(label)
      expect(controls).toHaveLength(2)
      expect(controls[0]).not.toBe(controls[1])
    }
    const ids = Array.from(document.querySelectorAll('[id]')).map((el) => el.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('the per-project selection does not filter the org-wide register', () => {
    renderPage('/stakeholders?project=p1')

    expect(lastOrgFilters()?.project_id).toBeUndefined()
  })
})

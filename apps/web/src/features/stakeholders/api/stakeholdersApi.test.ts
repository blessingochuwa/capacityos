import { describe, expect, it, vi } from 'vitest'
import { apiGet } from '@/api/client'
import { STAKEHOLDER_REGISTER_PAGE_SIZE, stakeholdersApi } from './stakeholdersApi'

vi.mock('@/api/client', () => ({
  apiGet: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  apiPost: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}))

const mockedApiGet = vi.mocked(apiGet)

describe('stakeholdersApi.listForOrganization (Phase 48)', () => {
  it('requests the first page with no filters by default', async () => {
    await stakeholdersApi.listForOrganization()

    expect(mockedApiGet).toHaveBeenLastCalledWith('/api/v1/stakeholders', {
      project_id: undefined,
      influence: undefined,
      interest: undefined,
      decision_authority: undefined,
      limit: STAKEHOLDER_REGISTER_PAGE_SIZE,
      offset: 0,
    })
  })

  it('passes every filter and the offset through as query parameters', async () => {
    await stakeholdersApi.listForOrganization({
      project_id: 'project-1',
      influence: 'high',
      interest: 'low',
      decision_authority: 'decision_maker',
      offset: 100,
    })

    expect(mockedApiGet).toHaveBeenLastCalledWith('/api/v1/stakeholders', {
      project_id: 'project-1',
      influence: 'high',
      interest: 'low',
      decision_authority: 'decision_maker',
      limit: STAKEHOLDER_REGISTER_PAGE_SIZE,
      offset: 100,
    })
  })

  it('never sends an organization id — the server derives it from the session', async () => {
    await stakeholdersApi.listForOrganization({ project_id: 'project-1' })

    const params = mockedApiGet.mock.lastCall?.[1] ?? {}
    expect(Object.keys(params)).not.toContain('organization_id')
  })
})

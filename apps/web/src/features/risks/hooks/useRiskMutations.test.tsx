import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import {
  QueryClient,
  QueryClientProvider,
  type QueryKey,
} from '@tanstack/react-query'
import { makeProjectRisk } from '@/test/fixtures'
import { risksApi } from '../api/risksApi'
import { useOrgRisks } from './useOrgRisks'
import { useCreateRisk, useDeleteRisk, useUpdateRisk } from './useRiskMutations'

vi.mock('../api/risksApi', () => ({
  risksApi: {
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    listForOrganization: vi.fn(),
  },
}))

const api = vi.mocked(risksApi)

/** Mirrors lib/queryClient.ts's 30s staleTime, so nothing but an explicit
 * invalidation can make a cached register entry refetch inside a test —
 * exactly the condition under which the register went stale before
 * Phase 49 (docs/adr/0049-risk-register-cache-invalidation.md). */
function setup() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, retry: false },
      mutations: { retry: false },
    },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, wrapper }
}

/** Each case is a hook returning a trigger, so the three differently typed
 * mutations share one signature. */
const MUTATIONS: [string, () => () => Promise<unknown>][] = [
  [
    'create',
    () => {
      const m = useCreateRisk('p1')
      return () => m.mutateAsync({ description: 'New risk' })
    },
  ],
  [
    'update',
    () => {
      const m = useUpdateRisk('p1')
      return () => m.mutateAsync({ riskId: 'r1', data: { status: 'closed' } })
    },
  ],
  [
    'delete',
    () => {
      const m = useDeleteRisk('p1')
      return () => m.mutateAsync('r1')
    },
  ],
]

/** Every cached variant a user can reach on /risks — the unfiltered first
 * page, a later page, and a fully filtered page — plus the edited
 * project's own list. */
const SHOULD_REFRESH: QueryKey[] = [
  ['org-risks', { offset: 0 }],
  ['org-risks', { status: 'open', offset: 50 }],
  ['org-risks', { project_id: 'p2', exposure: 'high', offset: 0 }],
  ['projects', 'p1', 'risks'],
]

/** Data a risk mutation on project p1 cannot change. */
const MUST_NOT_REFRESH: QueryKey[] = [
  ['projects', 'p2', 'risks'],
  ['org-stakeholders', { offset: 0 }],
  ['projects', 'p1', 'stakeholders'],
]

function seed(queryClient: QueryClient) {
  for (const key of [...SHOULD_REFRESH, ...MUST_NOT_REFRESH]) {
    queryClient.setQueryData(key, { seeded: key })
  }
}

beforeEach(() => {
  // resetAllMocks (not clearAllMocks) also drains queued *Once values, so
  // a test that fails before consuming one can't leak it into the next.
  vi.resetAllMocks()
  api.create.mockResolvedValue(makeProjectRisk())
  api.update.mockResolvedValue(makeProjectRisk())
  api.remove.mockResolvedValue(undefined)
})

describe('risk mutations refresh the org-wide Risk Register', () => {
  it('a successful edit refetches a mounted register, which then shows the edited risk', async () => {
    api.listForOrganization
      .mockResolvedValueOnce({
        items: [makeProjectRisk({ id: 'r1', status: 'open' })],
        total: 1,
      })
      .mockResolvedValueOnce({
        items: [makeProjectRisk({ id: 'r1', status: 'closed' })],
        total: 1,
      })
    const { wrapper } = setup()
    const { result } = renderHook(
      () => ({
        register: useOrgRisks({ offset: 0 }),
        update: useUpdateRisk('p1'),
      }),
      { wrapper },
    )
    await waitFor(() =>
      expect(result.current.register.data?.items[0].status).toBe('open'),
    )

    await act(async () => {
      await result.current.update.mutateAsync({
        riskId: 'r1',
        data: { status: 'closed' },
      })
    })

    await waitFor(() =>
      expect(result.current.register.data?.items[0].status).toBe('closed'),
    )
    expect(api.listForOrganization).toHaveBeenCalledTimes(2)
  })

  it.each(MUTATIONS)(
    'a successful %s invalidates every register variant and the project list, nothing else',
    async (_name, useTrigger) => {
      const { queryClient, wrapper } = setup()
      seed(queryClient)
      const { result } = renderHook(useTrigger, { wrapper })

      await act(async () => {
        await result.current()
      })

      for (const key of SHOULD_REFRESH) {
        expect(
          queryClient.getQueryState(key)?.isInvalidated,
          JSON.stringify(key),
        ).toBe(true)
      }
      for (const key of MUST_NOT_REFRESH) {
        expect(
          queryClient.getQueryState(key)?.isInvalidated,
          JSON.stringify(key),
        ).toBe(false)
      }
    },
  )

  it('a failed edit invalidates nothing and leaves the displayed register untouched', async () => {
    api.listForOrganization.mockResolvedValue({
      items: [makeProjectRisk({ id: 'r1', status: 'open' })],
      total: 1,
    })
    api.update.mockRejectedValueOnce(new Error('403 Forbidden'))
    const { queryClient, wrapper } = setup()
    seed(queryClient)
    // Mounted under ['org-risks', {}] — a key seed() did not populate, so
    // the hook really fetches instead of serving seeded placeholder data.
    const { result } = renderHook(
      () => ({ register: useOrgRisks(), update: useUpdateRisk('p1') }),
      { wrapper },
    )
    await waitFor(() =>
      expect(result.current.register.data?.items[0].status).toBe('open'),
    )
    const fetchesBefore = api.listForOrganization.mock.calls.length

    await act(async () => {
      await expect(
        result.current.update.mutateAsync({
          riskId: 'r1',
          data: { status: 'closed' },
        }),
      ).rejects.toThrow('403 Forbidden')
    })

    for (const key of [
      ...SHOULD_REFRESH,
      ...MUST_NOT_REFRESH,
      ['org-risks', {}],
    ]) {
      expect(
        queryClient.getQueryState(key)?.isInvalidated,
        JSON.stringify(key),
      ).toBe(false)
    }
    expect(api.listForOrganization).toHaveBeenCalledTimes(fetchesBefore)
    expect(result.current.register.data?.items[0].status).toBe('open')
    await waitFor(() => expect(result.current.update.isError).toBe(true))
  })
})

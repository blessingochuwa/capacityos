import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  useCreateStakeholder,
  useDeleteStakeholder,
  useUpdateStakeholder,
} from './useStakeholderMutations'

vi.mock('../api/stakeholdersApi', () => ({
  stakeholdersApi: {
    create: vi.fn().mockResolvedValue({}),
    update: vi.fn().mockResolvedValue({}),
    remove: vi.fn().mockResolvedValue(undefined),
  },
}))

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  })
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { invalidate, wrapper }
}

/** Both registers render on StakeholdersOverviewPage — every mutation
 * must refresh the project's own list AND the org-wide register. */
describe('stakeholder mutations invalidate both registers', () => {
  /** Each case is a hook returning a trigger, so the three differently
   * typed mutations share one signature. */
  const cases: [string, () => () => Promise<unknown>][] = [
    [
      'create',
      () => {
        const m = useCreateStakeholder('p1')
        return () => m.mutateAsync({ name: 'x', role: 'Sponsor' })
      },
    ],
    [
      'update',
      () => {
        const m = useUpdateStakeholder('p1')
        return () => m.mutateAsync({ stakeholderId: 's1', data: { role: 'y' } })
      },
    ],
    [
      'delete',
      () => {
        const m = useDeleteStakeholder('p1')
        return () => m.mutateAsync('s1')
      },
    ],
  ]

  it.each(cases)('%s', async (_name, useHook) => {
    const { invalidate, wrapper } = setup()
    const { result } = renderHook(useHook, { wrapper })

    await act(async () => {
      await result.current()
    })

    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ['projects', 'p1', 'stakeholders'],
    })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['org-stakeholders'] })
  })
})

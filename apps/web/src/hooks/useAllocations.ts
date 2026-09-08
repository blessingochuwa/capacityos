import { useQuery } from '@tanstack/react-query'
import { allocationsApi } from '@/api/entities'

/** Every allocation in the caller's active organization (Phase 42) — reused
 * by the Capacity vs. Priority matrix to derive each project's total
 * allocated hours client-side. Mirrors useProjects/useTeams exactly. */
export function useAllocations() {
  return useQuery({
    queryKey: ['allocations'],
    queryFn: allocationsApi.list,
  })
}

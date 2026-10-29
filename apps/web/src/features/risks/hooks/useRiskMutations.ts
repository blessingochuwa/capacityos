import {
  useMutation,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query'
import { risksApi } from '../api/risksApi'
import type { RiskCreateInput, RiskUpdateInput } from '../api/risksApi'

/** Refreshes the edited project's own register AND the org-wide register
 * (`['org-risks', filters]` — every filter/page variant). Both render on
 * RisksOverviewPage, so an edit in one must never leave the other stale.
 * Runs only in onSuccess: a failed mutation changed nothing server-side,
 * so it must not trigger a refetch. Mirrors useStakeholderMutations
 * (Phase 48). See docs/adr/0049-risk-register-cache-invalidation.md. */
function invalidateRiskQueries(queryClient: QueryClient, projectId: string) {
  void queryClient.invalidateQueries({
    queryKey: ['projects', projectId, 'risks'],
  })
  void queryClient.invalidateQueries({ queryKey: ['org-risks'] })
}

export function useCreateRisk(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: RiskCreateInput) => risksApi.create(projectId, data),
    onSuccess: () => invalidateRiskQueries(queryClient, projectId),
  })
}

export function useUpdateRisk(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ riskId, data }: { riskId: string; data: RiskUpdateInput }) =>
      risksApi.update(projectId, riskId, data),
    onSuccess: () => invalidateRiskQueries(queryClient, projectId),
  })
}

export function useDeleteRisk(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (riskId: string) => risksApi.remove(projectId, riskId),
    onSuccess: () => invalidateRiskQueries(queryClient, projectId),
  })
}

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { scenariosApi } from '../api/scenariosApi'
import type { ScenarioPriorityOverrideSetInput } from '../api/scenariosApi'

function invalidatePriorityQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  scenarioId: string,
) {
  void queryClient.invalidateQueries({
    queryKey: ['scenarios', scenarioId, 'priority-overrides'],
  })
  void queryClient.invalidateQueries({
    queryKey: ['scenarios', scenarioId, 'priority-comparison'],
  })
}

export function useSetScenarioPriorityOverride(scenarioId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ScenarioPriorityOverrideSetInput) =>
      scenariosApi.setPriorityOverride(scenarioId, data),
    onSuccess: () => invalidatePriorityQueries(queryClient, scenarioId),
  })
}

export function useDeleteScenarioPriorityOverride(scenarioId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (overrideId: string) =>
      scenariosApi.deletePriorityOverride(scenarioId, overrideId),
    onSuccess: () => invalidatePriorityQueries(queryClient, scenarioId),
  })
}

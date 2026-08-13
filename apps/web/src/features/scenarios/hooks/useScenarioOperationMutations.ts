import { useMutation, useQueryClient } from '@tanstack/react-query'
import { scenariosApi } from '../api/scenariosApi'
import type { ScenarioOperationPayload } from '../types/scenario'

/** Editing the change list invalidates ONLY the operations list. Results
 * and comparison are deliberately left alone here — if they were
 * invalidated too, an already-mounted, already-enabled results/comparison
 * query (ScenarioWorkspacePage, after the first Calculate) would
 * auto-refetch in the background on every add/edit/remove, which is
 * exactly the "recalculate on every keystroke" behavior prompt §13
 * forbids. Staleness after this point is tracked in the UI (comparing
 * operationsQuery.dataUpdatedAt against when results were last computed)
 * and surfaced as a "recalculate" prompt instead — see ScenarioWorkspacePage. */
function invalidateOperations(
  queryClient: ReturnType<typeof useQueryClient>,
  scenarioId: string,
): void {
  void queryClient.invalidateQueries({
    queryKey: ['scenarios', scenarioId, 'operations'],
  })
}

export function useCreateScenarioOperation(scenarioId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ScenarioOperationPayload) =>
      scenariosApi.createOperation(scenarioId, payload),
    onSuccess: () => invalidateOperations(queryClient, scenarioId),
  })
}

export function useUpdateScenarioOperation(scenarioId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      operationId,
      payload,
    }: {
      operationId: string
      payload: ScenarioOperationPayload
    }) => scenariosApi.updateOperation(scenarioId, operationId, payload),
    onSuccess: () => invalidateOperations(queryClient, scenarioId),
  })
}

export function useDeleteScenarioOperation(scenarioId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (operationId: string) =>
      scenariosApi.deleteOperation(scenarioId, operationId),
    onSuccess: () => invalidateOperations(queryClient, scenarioId),
  })
}

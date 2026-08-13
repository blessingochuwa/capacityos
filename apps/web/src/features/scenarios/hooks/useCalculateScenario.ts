import { useMutation, useQueryClient } from '@tanstack/react-query'
import { scenariosApi } from '../api/scenariosApi'

/** The explicit "Calculate" action (prompt §13: never recalculate on every
 * keystroke). Seeds the results query cache directly with the response
 * (calculate returns the same shape as GET /results — see
 * apps/api/app/api/v1/scenarios.py) so the workspace shows results
 * immediately without a redundant extra fetch, and invalidates comparison
 * so it's refetched fresh against the same recalculated state. */
export function useCalculateScenario(scenarioId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => scenariosApi.calculate(scenarioId),
    onSuccess: (results) => {
      queryClient.setQueryData(['scenarios', scenarioId, 'results'], results)
      void queryClient.invalidateQueries({
        queryKey: ['scenarios', scenarioId, 'comparison'],
      })
    },
  })
}

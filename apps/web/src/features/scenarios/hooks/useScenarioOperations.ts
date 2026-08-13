import { useQuery } from '@tanstack/react-query'
import { scenariosApi } from '../api/scenariosApi'

export function useScenarioOperations(
  scenarioId: string | undefined,
  enabled = true,
) {
  return useQuery({
    queryKey: ['scenarios', scenarioId, 'operations'],
    queryFn: () => {
      if (!scenarioId)
        throw new Error('useScenarioOperations called without a scenarioId')
      return scenariosApi.listOperations(scenarioId)
    },
    enabled: scenarioId !== undefined && enabled,
  })
}

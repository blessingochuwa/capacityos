import { useQuery } from '@tanstack/react-query'
import { scenariosApi } from '../api/scenariosApi'

export function useScenarioComparison(
  scenarioId: string | undefined,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ['scenarios', scenarioId, 'comparison'],
    queryFn: () => {
      if (!scenarioId)
        throw new Error('useScenarioComparison called without a scenarioId')
      return scenariosApi.getComparison(scenarioId)
    },
    enabled: scenarioId !== undefined && enabled,
  })
}

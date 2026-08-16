import { useQuery } from '@tanstack/react-query'
import { insightsApi } from '../api/insightsApi'

export function useScenarioSignals(
  scenarioId: string | undefined,
  enabled: boolean = true,
) {
  return useQuery({
    queryKey: ['insights', 'scenario', scenarioId],
    queryFn: () => {
      if (!scenarioId)
        throw new Error('useScenarioSignals called without a scenarioId')
      return insightsApi.getScenarioSignals(scenarioId)
    },
    enabled: scenarioId !== undefined && enabled,
  })
}

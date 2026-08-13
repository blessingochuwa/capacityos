import { useQuery } from '@tanstack/react-query'
import { scenariosApi } from '../api/scenariosApi'

export function useScenario(scenarioId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['scenarios', scenarioId],
    queryFn: () => {
      if (!scenarioId)
        throw new Error('useScenario called without a scenarioId')
      return scenariosApi.get(scenarioId)
    },
    enabled: scenarioId !== undefined && enabled,
  })
}

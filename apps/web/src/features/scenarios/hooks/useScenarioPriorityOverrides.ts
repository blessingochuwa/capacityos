import { useQuery } from '@tanstack/react-query'
import { scenariosApi } from '../api/scenariosApi'

export function useScenarioPriorityOverrides(scenarioId: string | undefined) {
  return useQuery({
    queryKey: ['scenarios', scenarioId, 'priority-overrides'],
    queryFn: () => scenariosApi.listPriorityOverrides(scenarioId as string),
    enabled: scenarioId !== undefined,
  })
}

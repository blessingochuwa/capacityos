import { useQuery } from '@tanstack/react-query'
import { scenariosApi } from '../api/scenariosApi'

export function useScenarioPriorityComparison(
  scenarioId: string | undefined,
  frameworkId: string | undefined,
) {
  return useQuery({
    queryKey: ['scenarios', scenarioId, 'priority-comparison', frameworkId],
    queryFn: () => scenariosApi.getPriorityComparison(scenarioId as string, frameworkId as string),
    enabled: scenarioId !== undefined && frameworkId !== undefined,
  })
}

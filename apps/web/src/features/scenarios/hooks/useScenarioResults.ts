import { useQuery } from '@tanstack/react-query'
import { scenariosApi } from '../api/scenariosApi'

/** Results are fetched on demand (not on every operation-list change) —
 * see useCalculateScenario, which is the explicit "Calculate" action
 * (CLAUDE.md-aligned prompt §13: never recalculate on every keystroke). */
export function useScenarioResults(
  scenarioId: string | undefined,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ['scenarios', scenarioId, 'results'],
    queryFn: () => {
      if (!scenarioId)
        throw new Error('useScenarioResults called without a scenarioId')
      return scenariosApi.getResults(scenarioId)
    },
    enabled: scenarioId !== undefined && enabled,
  })
}

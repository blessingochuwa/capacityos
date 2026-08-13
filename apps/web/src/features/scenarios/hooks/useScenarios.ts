import { useQuery } from '@tanstack/react-query'
import { scenariosApi } from '../api/scenariosApi'
import type { ScenarioStatus } from '../types/scenario'

export function useScenarios(status?: ScenarioStatus) {
  return useQuery({
    queryKey: ['scenarios', 'list', status],
    queryFn: () => scenariosApi.list(status),
  })
}

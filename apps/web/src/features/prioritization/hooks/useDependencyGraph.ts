import { useQuery } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'

export function useDependencyGraph() {
  return useQuery({
    queryKey: ['prioritization', 'dependency-graph'],
    queryFn: () => prioritizationApi.getDependencyGraph(),
  })
}

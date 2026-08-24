import { useQuery } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'

export function useFrameworks(isActive?: boolean) {
  return useQuery({
    queryKey: ['prioritization', 'frameworks', { isActive }],
    queryFn: () => prioritizationApi.listFrameworks(isActive),
  })
}

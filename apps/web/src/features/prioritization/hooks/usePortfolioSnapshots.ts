import { useQuery } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'

export function usePortfolioSnapshots(frameworkId: string | undefined) {
  return useQuery({
    queryKey: ['prioritization', 'snapshots', frameworkId],
    queryFn: () => prioritizationApi.listSnapshots(frameworkId),
    enabled: frameworkId !== undefined,
  })
}

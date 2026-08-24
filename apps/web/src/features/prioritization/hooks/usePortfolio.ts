import { useQuery } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'

export function usePortfolio(frameworkId: string | undefined) {
  return useQuery({
    queryKey: ['prioritization', 'portfolio', frameworkId],
    queryFn: () => prioritizationApi.rankPortfolio(frameworkId as string),
    enabled: frameworkId !== undefined,
  })
}

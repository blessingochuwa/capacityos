import { useQuery } from '@tanstack/react-query'
import { risksApi } from '../api/risksApi'

export function useRisks(projectId: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectId, 'risks'],
    queryFn: () => risksApi.listForProject(projectId as string),
    enabled: projectId !== undefined,
  })
}

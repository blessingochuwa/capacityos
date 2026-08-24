import { useQuery } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'

export function useProjectPriorityScores(projectId: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectId, 'priority-scores'],
    queryFn: () => prioritizationApi.listScoresForProject(projectId as string),
    enabled: projectId !== undefined,
  })
}

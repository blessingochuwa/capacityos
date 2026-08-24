import { useQuery } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'

export function useProjectDependencies(projectId: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectId, 'dependencies'],
    queryFn: () => prioritizationApi.listDependenciesForProject(projectId as string),
    enabled: projectId !== undefined,
  })
}

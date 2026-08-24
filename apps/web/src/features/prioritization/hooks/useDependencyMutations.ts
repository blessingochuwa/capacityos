import { useMutation, useQueryClient } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'
import type { DependencyCreateInput } from '../api/prioritizationApi'

function invalidateDependencyQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string,
) {
  void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'dependencies'] })
  void queryClient.invalidateQueries({ queryKey: ['prioritization', 'dependency-graph'] })
}

export function useCreateDependency(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: DependencyCreateInput) =>
      prioritizationApi.createDependency(projectId, data),
    onSuccess: () => invalidateDependencyQueries(queryClient, projectId),
  })
}

export function useDeleteDependency(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (dependencyId: string) =>
      prioritizationApi.deleteDependency(projectId, dependencyId),
    onSuccess: () => invalidateDependencyQueries(queryClient, projectId),
  })
}

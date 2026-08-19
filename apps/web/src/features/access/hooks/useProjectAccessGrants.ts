import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { accessGrantsApi } from '../api/accessGrantsApi'

export function useProjectAccessGrants(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-access-grants', projectId],
    queryFn: () => accessGrantsApi.listForProject(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useGrantProjectAccess(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => accessGrantsApi.grantProject(projectId, userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project-access-grants', projectId] })
    },
  })
}

export function useRevokeProjectAccess(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => accessGrantsApi.revokeProject(projectId, userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['project-access-grants', projectId] })
    },
  })
}

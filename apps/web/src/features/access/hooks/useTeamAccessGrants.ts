import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { accessGrantsApi } from '../api/accessGrantsApi'

export function useTeamAccessGrants(teamId: string | undefined) {
  return useQuery({
    queryKey: ['team-access-grants', teamId],
    queryFn: () => accessGrantsApi.listForTeam(teamId as string),
    enabled: Boolean(teamId),
  })
}

export function useGrantTeamAccess(teamId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => accessGrantsApi.grantTeam(teamId, userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['team-access-grants', teamId] })
    },
  })
}

export function useRevokeTeamAccess(teamId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => accessGrantsApi.revokeTeam(teamId, userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['team-access-grants', teamId] })
    },
  })
}

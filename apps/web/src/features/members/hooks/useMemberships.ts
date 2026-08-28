import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { UserRole } from '@/features/auth/types/auth'
import { membersApi } from '../api/membersApi'

/** Keyed by organizationId so switching the active organization (which
 * purges the whole query cache anyway — see AuthContext) can never show a
 * stale roster. */
export function useMemberships(organizationId: string | undefined) {
  return useQuery({
    queryKey: ['memberships', organizationId],
    queryFn: () => membersApi.list(organizationId as string),
    enabled: Boolean(organizationId),
  })
}

export function useAddMember(organizationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { email: string; role: UserRole }) =>
      membersApi.add(organizationId, vars.email, vars.role),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['memberships', organizationId] })
    },
  })
}

export function useChangeMemberRole(organizationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { userId: string; role: UserRole }) =>
      membersApi.changeRole(organizationId, vars.userId, vars.role),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['memberships', organizationId] })
    },
  })
}

export function useRevokeMember(organizationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => membersApi.revoke(organizationId, userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['memberships', organizationId] })
    },
  })
}

export function useReactivateMember(organizationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => membersApi.reactivate(organizationId, userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['memberships', organizationId] })
    },
  })
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { SESSION_QUERY_KEY } from '@/features/auth/context/AuthContext'
import { organizationApi } from '../api/organizationApi'

export function useOrganization(organizationId: string | undefined) {
  return useQuery({
    queryKey: ['organization', organizationId],
    queryFn: () => organizationApi.get(organizationId as string),
    enabled: Boolean(organizationId),
  })
}

export function useRenameOrganization(organizationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => organizationApi.rename(organizationId, name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['organization', organizationId] })
      // /auth/me carries `active_organization.name`, which the header
      // switcher and user menu render — refetch it so the new name shows
      // everywhere, not just on this page.
      void queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY })
    },
  })
}

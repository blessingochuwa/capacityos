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

/** Phase 31 backend contract: 200 flips only `is_active`; 422 when the
 * organization has fewer than 2 active Owners (the backend is the sole
 * authority on that count — Phase 32 never re-derives it). On success the
 * organization is inactive, so every org-scoped query will now 409 until
 * it's reactivated while /auth/me keeps resolving — revalidate everything
 * so each surface refetches into its correct state (this settings page
 * into the recovery panel, other pages into a clean "no longer active"
 * error) instead of showing stale, now-inaccessible data. */
export function useDeactivateOrganization(organizationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => organizationApi.deactivate(organizationId),
    onSuccess: () => {
      void queryClient.invalidateQueries()
    },
  })
}

/** Phase 31 backend contract: restores `is_active=True`, idempotent,
 * never touches a membership or any other row. Authorized for an active
 * Owner membership of the target org only (403/404 otherwise). Access is
 * restored with no re-login (Phase 31, verified) — revalidate every query
 * so the app returns to its normal state. */
export function useReactivateOrganization(organizationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => organizationApi.reactivate(organizationId),
    onSuccess: () => {
      void queryClient.invalidateQueries()
    },
  })
}

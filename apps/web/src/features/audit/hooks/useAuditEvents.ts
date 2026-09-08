import { useQuery } from '@tanstack/react-query'
import { auditApi, type AuditEventFilters } from '../api/auditApi'

/** Keyed `['audit-events', filters]`, mirroring
 * features/users/hooks/useUserAccounts.ts's `['user-accounts', filters]`
 * exactly — a filter/offset change is a distinct cached query, never a
 * client-side re-filter of an already-fetched page. No organization id is
 * threaded into the key: switching organizations purges the entire query
 * cache (features/auth/context/AuthContext.tsx's `switchOrganization`
 * mutation), the same established mechanism every other organization-
 * scoped query in this app already relies on — see docs/adr/0012. */
export function useAuditEvents(filters: AuditEventFilters = {}) {
  return useQuery({
    queryKey: ['audit-events', filters],
    queryFn: () => auditApi.list(filters),
  })
}

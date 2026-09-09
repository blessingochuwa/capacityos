import { useQuery } from '@tanstack/react-query'
import { risksApi, type OrgRiskFilters } from '../api/risksApi'

/** Keyed `['org-risks', filters]`, mirroring
 * features/audit/hooks/useAuditEvents.ts's `['audit-events', filters]`
 * exactly — a filter/offset change is a distinct cached query, never a
 * client-side re-filter of an already-fetched page. No organization id
 * is threaded into the key: switching organizations purges the entire
 * query cache (features/auth/context/AuthContext.tsx's
 * `switchOrganization` mutation), the same mechanism every other
 * organization-scoped query in this app already relies on. */
export function useOrgRisks(filters: OrgRiskFilters = {}) {
  return useQuery({
    queryKey: ['org-risks', filters],
    queryFn: () => risksApi.listForOrganization(filters),
  })
}

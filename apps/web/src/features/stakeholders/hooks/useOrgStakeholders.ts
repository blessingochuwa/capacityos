import { useQuery } from '@tanstack/react-query'
import { stakeholdersApi, type OrgStakeholderFilters } from '../api/stakeholdersApi'

/** Keyed `['org-stakeholders', filters]`, mirroring useOrgRisks's
 * `['org-risks', filters]` — every filter and the offset are part of the
 * key, so a filter/page change is a distinct cached query, never a
 * client-side re-filter of an already-fetched page. No organization id is
 * threaded into the key: switching organizations purges the entire query
 * cache (features/auth/context/AuthContext.tsx), and the server scopes
 * every row to the session's organization regardless. */
export function useOrgStakeholders(filters: OrgStakeholderFilters = {}) {
  return useQuery({
    queryKey: ['org-stakeholders', filters],
    queryFn: () => stakeholdersApi.listForOrganization(filters),
  })
}

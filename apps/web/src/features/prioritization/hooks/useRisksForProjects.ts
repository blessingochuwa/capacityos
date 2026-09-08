import { useQueries } from '@tanstack/react-query'
import { risksApi } from '@/features/risks/api/risksApi'

/**
 * Fires one GET /api/v1/projects/{id}/risks per project id, in parallel
 * (Phase 45 — Risk vs. Value quadrant). There is no org-wide "list every
 * risk" endpoint (ADR 0013: "No org-wide/cross-project risk register —
 * every route is nested under one project"), so this is the smallest
 * client-side composition over the existing, unchanged, already-
 * authorized per-project route — the same route features/risks/ already
 * calls (`useRisks`), reusing its EXACT query key shape
 * (`['projects', projectId, 'risks']`) so results share cache with the
 * standalone Risks page rather than duplicating it.
 *
 * Each individual query is already `Permission.RISK_READ`-gated (granted
 * to every role, matching `PRIORITIZATION_READ`'s precedent) and already
 * organization-scoped server-side (`RiskService.list_for_project`) — this
 * hook adds no authorization or tenancy logic of its own and accepts no
 * organization id.
 */
export function useRisksForProjects(projectIds: string[]) {
  return useQueries({
    queries: projectIds.map((projectId) => ({
      queryKey: ['projects', projectId, 'risks'],
      queryFn: () => risksApi.listForProject(projectId),
    })),
  })
}

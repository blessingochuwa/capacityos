import { apiGet, apiPatch } from '@/api/client'
import type { Organization } from '../types/organization'

/** Thin typed wrappers over apps/api's Phase 12 organization
 * read/update endpoints (apps/api/app/api/v1/organizations.py). Both are
 * gated by Permission.ORGANIZATION_MANAGE (Owner only) and by
 * `_require_active_organization` — the path id must be the caller's own
 * active organization, or the backend 404s exactly like a nonexistent one
 * (no IDOR). This module adds no client-side authorization; it surfaces
 * the backend's 403/404/422 verbatim (Phase 30).
 *
 * The deactivate endpoint (POST .../{id}/deactivate) is deliberately NOT
 * wrapped here — it is irreversible through the product (no reactivation
 * path exists) and locks out every member including the acting Owner, so
 * exposing it was deferred pending a backend guard / reactivation path.
 * See docs/adr/0030-organization-settings-ui.md. */
export const organizationApi = {
  get: (organizationId: string) =>
    apiGet<Organization>(`/api/v1/organizations/${organizationId}`),

  rename: (organizationId: string, name: string) =>
    apiPatch<Organization>(`/api/v1/organizations/${organizationId}`, { name }),
}

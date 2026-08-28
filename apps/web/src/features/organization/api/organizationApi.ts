import { apiGet, apiPatch, apiPost } from '@/api/client'
import type { Organization } from '../types/organization'

/** Thin typed wrappers over apps/api's Phase 12/30/31 organization
 * lifecycle endpoints (apps/api/app/api/v1/organizations.py).
 *
 * `get`/`rename`/`deactivate` are gated by
 * Permission.ORGANIZATION_MANAGE (Owner only) and by
 * `_require_active_organization` — the path id must be the caller's own
 * active organization, or the backend 404s exactly like a nonexistent
 * one (no IDOR). `reactivate` (Phase 31) deliberately does NOT depend on
 * an active-organization context — a deactivated org can't provide one —
 * so the backend authorizes it by resolving the caller's Owner
 * membership in the target org directly; a non-Owner gets 403, a
 * non-member gets 404.
 *
 * This module adds no client-side authorization or safety logic: the
 * >= 2-active-Owner deactivation guard (422) and every other check stay
 * authoritative on the backend and are surfaced verbatim (Phase 32). */
export const organizationApi = {
  get: (organizationId: string) =>
    apiGet<Organization>(`/api/v1/organizations/${organizationId}`),

  rename: (organizationId: string, name: string) =>
    apiPatch<Organization>(`/api/v1/organizations/${organizationId}`, { name }),

  deactivate: (organizationId: string) =>
    apiPost<Organization>(`/api/v1/organizations/${organizationId}/deactivate`),

  reactivate: (organizationId: string) =>
    apiPost<Organization>(`/api/v1/organizations/${organizationId}/reactivate`),
}

import { apiGet } from '@/api/client'
import type { Page } from '@/types/entities'
import type { AuditEvent } from '../types/audit'

/** Thin typed wrapper over apps/api's Phase 10 audit endpoint
 * (apps/api/app/api/v1/audit.py). Already gated by
 * Permission.AUDIT_READ (Admin/Owner) and already scoped to the caller's
 * active organization server-side (`get_current_membership` —
 * app/api/deps.py); this module adds no client-side authorization or
 * scoping and accepts no organization id — it cannot request another
 * organization's events even if asked to (Phase 43). */

/** The page size this UI requests. Fixed, not user-configurable — the
 * existing `GET /api/v1/audit` route allows any value 1-500
 * (`Query(default=100, ge=1, le=500)`); 50 keeps a single page's table
 * short enough to scan while still making the Previous/Next controls
 * meaningful for an org with real history. */
export const AUDIT_PAGE_SIZE = 50

export interface AuditEventFilters {
  /** Exact match against a specific actor's user id — apps/api's
   * `actor_user_id` query param. Populated from the active organization's
   * membership roster (features/members), never free text, since a raw
   * UUID isn't something a person can usefully type. */
  actor_user_id?: string
  /** Exact match against `AuditEvent.action`
   * (`apps/api/app/repositories/audit_event.py::list_filtered` —
   * `AuditEvent.action == action`, not a substring/`ilike` search) — see
   * `apps/api/app/models/enums.py::AuditAction`'s own docstring: an open,
   * backend-owned vocabulary, so this is a plain text field (Phase 44),
   * never a dropdown built from an invented or partial list. */
  action?: string
  /** Exact match against `AuditEvent.resource_type` — same semantics and
   * same reasoning as `action` above. */
  resource_type?: string
  /** Inclusive lower/upper bounds on `timestamp`, ISO 8601 — apps/api's
   * `start`/`end` query params. */
  start?: string
  end?: string
  offset?: number
}

export const auditApi = {
  list: (filters: AuditEventFilters = {}) =>
    apiGet<Page<AuditEvent>>('/api/v1/audit', {
      actor_user_id: filters.actor_user_id || undefined,
      action: filters.action || undefined,
      resource_type: filters.resource_type || undefined,
      start: filters.start || undefined,
      end: filters.end || undefined,
      limit: AUDIT_PAGE_SIZE,
      offset: filters.offset ?? 0,
    }),
}

/**
 * Mirrors apps/api/app/schemas/audit.py::AuditEventRead verbatim — see
 * src/types/entities.ts's header comment for why these types are
 * hand-written, not generated (Phase 43).
 */

/** apps/api/app/models/enums.py::AuditOutcome — a small, closed, DB
 * CHECK-constrained vocabulary (unlike `action` below). */
export type AuditOutcome = 'success' | 'failure' | 'denied'

export interface AuditEvent {
  id: string
  timestamp: string
  organization_id: string | null
  actor_user_id: string | null
  /** Denormalized at write time (apps/api/app/models/audit_event.py) so a
   * record stays readable even after the acting user is renamed or
   * deactivated. Null for an event with no identifiable actor (e.g. a
   * login failure against an unknown email). */
  actor_email: string | null
  /** apps/api/app/models/enums.py::AuditAction — an open, backend-owned
   * vocabulary ("new audited actions are a pure code change, never a
   * migration"). Rendered verbatim here, never mapped through an invented
   * human-readable label table that would silently go stale for a new
   * action. */
  action: string
  resource_type: string | null
  resource_id: string | null
  outcome: AuditOutcome
  request_id: string | null
  /** Deliberately minimal per action type at write time — never a raw
   * request body, file content, or secret (see the model's own docstring
   * and tests/api/test_audit.py). Rendered as-is; this UI does not expand
   * what the backend already decided is safe to expose. */
  event_metadata: Record<string, unknown> | null
}

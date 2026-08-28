import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import type { UserRole } from '@/features/auth/types/auth'
import type { Page } from '@/types/entities'
import type { Membership } from '../types/members'

/** Thin typed wrappers over apps/api's Phase 12/15 membership-management
 * endpoints (apps/api/app/api/v1/organizations.py). Every route is already
 * gated by Permission.MEMBERSHIP_MANAGE (Admin/Owner), already scoped to
 * the caller's active organization (a path organization_id that isn't the
 * caller's active org 404s — _require_active_organization), already
 * audited, and already enforces the Owner-escalation rule and the Phase 15
 * last-owner invariant. This module adds no client-side authorization —
 * it surfaces the backend's 403/422/404/409 verbatim (Phase 28). */

const LIST_ALL_LIMIT = 500

export const membersApi = {
  list: (organizationId: string) =>
    apiGet<Page<Membership>>(
      `/api/v1/organizations/${organizationId}/memberships`,
      { limit: LIST_ALL_LIMIT },
    ),

  /** Adds an EXISTING account by email — no account is created if none
   * matches (apps/api returns 404, same as any other missing resource;
   * CLAUDE.md §26). */
  add: (organizationId: string, email: string, role: UserRole) =>
    apiPost<Membership>(`/api/v1/organizations/${organizationId}/memberships`, {
      email,
      role,
    }),

  changeRole: (organizationId: string, userId: string, role: UserRole) =>
    apiPatch<Membership>(
      `/api/v1/organizations/${organizationId}/memberships/${userId}/role`,
      { role },
    ),

  revoke: (organizationId: string, userId: string) =>
    apiDelete(`/api/v1/organizations/${organizationId}/memberships/${userId}`),

  reactivate: (organizationId: string, userId: string) =>
    apiPost<Membership>(
      `/api/v1/organizations/${organizationId}/memberships/${userId}/reactivate`,
    ),
}

/**
 * Mirrors apps/api/app/schemas/auth.py::MeRead verbatim — see
 * src/types/entities.ts's header comment for why these types are
 * hand-written, not generated.
 */

export type UserRole = 'owner' | 'admin' | 'manager' | 'member' | 'viewer'
export type UserStatus = 'active' | 'invited' | 'disabled'

/** The minimal shape returned for both the caller's active organization and
 * every organization in their `organizations` list — see
 * apps/api/app/schemas/auth.py::OrganizationSummary. */
export interface OrganizationSummary {
  id: string
  name: string
  slug: string
  /** Phase 33 — the persisted `Organization.is_active`, sent straight
   * through `/auth/me` so the shell can render a global inactive-org
   * banner and the switcher can stop offering a deactivated org, without
   * probing an org-scoped endpoint that would just 409. Informational
   * only; the backend re-checks `is_active` per request and stays the
   * authorization boundary. */
  is_active: boolean
}

export interface CurrentUser {
  id: string
  email: string
  display_name: string
  status: UserStatus
  person_id: string | null
  last_login_at: string | null
  created_at: string
  updated_at: string
  /** Phase 12: relative to `active_organization`, never global — `null`
   * (with `permissions`/`accessible_*_ids` all empty) whenever
   * active_organization is null, which happens right after login for an
   * account with zero or multiple memberships, before an explicit
   * switch-organization call. See
   * docs/adr/0012-organizations-multi-tenancy.md. */
  role: UserRole | null
  active_organization: OrganizationSummary | null
  /** Every ACTIVE membership's organization, for the switcher UI — not the
   * caller's full account history (a revoked membership's organization
   * isn't selectable). */
  organizations: OrganizationSummary[]
  /** The authoritative source for frontend UI gating — see
   * apps/api/app/schemas/auth.py::me_to_read. Never re-derived from
   * `role` on this side; the backend is the one place the role/permission
   * table is decided (CLAUDE.md §21: backend authorization is the security
   * boundary, frontend authorization is for UX only). */
  permissions: string[]
  /** Phase 11: this user's own explicit instance-level grants, within the
   * ACTIVE organization. Only meaningful for Manager — Owner/Admin bypass
   * resource scoping entirely on the backend (role-based, not grant-based),
   * so the frontend should treat those two roles as always-authorized
   * regardless of what these lists contain. Member/Viewer hold no
   * team.write/project.write permission to begin with, so an empty list
   * for them isn't a restriction, just accurate. See
   * docs/adr/0011-instance-level-resource-authorization.md. */
  accessible_team_ids: string[]
  accessible_project_ids: string[]
}

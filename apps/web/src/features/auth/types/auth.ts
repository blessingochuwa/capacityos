/**
 * Mirrors apps/api/app/schemas/user.py::UserRead verbatim — see
 * src/types/entities.ts's header comment for why these types are
 * hand-written, not generated.
 */

export type UserRole = 'owner' | 'admin' | 'manager' | 'member' | 'viewer'
export type UserStatus = 'active' | 'invited' | 'disabled'

export interface CurrentUser {
  id: string
  email: string
  display_name: string
  status: UserStatus
  role: UserRole
  person_id: string | null
  last_login_at: string | null
  created_at: string
  updated_at: string
  /** The authoritative source for frontend UI gating — see
   * apps/api/app/schemas/user.py::user_to_read. Never re-derived from
   * `role` on this side; the backend is the one place the role/permission
   * table is decided (CLAUDE.md §21: backend authorization is the security
   * boundary, frontend authorization is for UX only). */
  permissions: string[]
  /** Phase 11: this user's own explicit instance-level grants. Only
   * meaningful for Manager — Owner/Admin bypass resource scoping entirely
   * on the backend (role-based, not grant-based), so the frontend should
   * treat those two roles as always-authorized regardless of what these
   * lists contain. Member/Viewer hold no team.write/project.write
   * permission to begin with, so an empty list for them isn't a
   * restriction, just accurate. See
   * docs/adr/0011-instance-level-resource-authorization.md. */
  accessible_team_ids: string[]
  accessible_project_ids: string[]
}

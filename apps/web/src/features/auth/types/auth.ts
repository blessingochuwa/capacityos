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
}

/**
 * Mirrors apps/api/app/schemas/user.py::UserRead verbatim — see
 * src/types/entities.ts's header comment for why these types are
 * hand-written, not generated (Phase 29).
 *
 * A `User` is the global login identity: a unique email, a display name,
 * account `status`, an optional link to one `Person`, and lockout/login
 * metadata. It carries no role and belongs to no organization — role lives
 * on `OrganizationMembership` (Phase 12 / see features/members/), and the
 * only organization-scoped thing here is which `Person` the account may
 * link to.
 */

/** apps/api/app/models/enums.py::UserStatus. `invited` exists for a future
 * invite flow that does not exist yet; like `disabled`, it blocks login
 * entirely (AuthService.login refuses any non-`active` status). This UI
 * only ever *sets* `active` or `disabled`. */
export type UserStatus = 'active' | 'invited' | 'disabled'

export interface UserAccount {
  id: string
  email: string
  display_name: string
  status: UserStatus
  person_id: string | null
  last_login_at: string | null
  created_at: string
  updated_at: string
}

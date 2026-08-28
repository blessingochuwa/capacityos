/**
 * Mirrors apps/api/app/schemas/organization_membership.py::MembershipRead
 * verbatim — see src/types/entities.ts's header comment for why these types
 * are hand-written, not generated (Phase 28).
 *
 * `MembershipRead` is composed server-side from the OrganizationMembership
 * row and its linked User (membership_to_read), so `email`/`display_name`
 * are always present alongside the membership's own `role`/`status`.
 */

import type { UserRole } from '@/features/auth/types/auth'

/** apps/api/app/models/enums.py::MembershipStatus — distinct from a User
 * account's own status: this governs whether THIS organization membership is
 * currently in effect, not whether the account can log in at all. */
export type MembershipStatus = 'active' | 'revoked'

export interface Membership {
  id: string
  organization_id: string
  user_id: string
  email: string
  display_name: string
  role: UserRole
  status: MembershipStatus
  created_at: string
  updated_at: string
}

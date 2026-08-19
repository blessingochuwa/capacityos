/**
 * Mirrors apps/api/app/schemas/access_grant.py's Read schemas verbatim —
 * see src/types/entities.ts's header comment for why these types are
 * hand-written, not generated (Phase 11).
 */

export interface TeamAccessGrant {
  id: string
  user_id: string
  team_id: string
  granted_by_user_id: string | null
  created_at: string
}

export interface ProjectAccessGrant {
  id: string
  user_id: string
  project_id: string
  granted_by_user_id: string | null
  created_at: string
}

/** A minimal projection of apps/api's UserRead — only the fields the
 * access-management picker/table need, not the full identity/permission
 * shape features/auth/types/auth.ts::CurrentUser already covers for the
 * signed-in user themselves. */
export interface UserSummary {
  id: string
  email: string
  display_name: string
  role: string
}

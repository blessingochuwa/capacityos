import { apiDelete, apiGet, apiPost } from '@/api/client'
import type { Page } from '@/types/entities'
import type { ProjectAccessGrant, TeamAccessGrant, UserSummary } from '../types/access'

/** Thin typed wrappers over apps/api's Phase 11 access-grant management
 * endpoints (apps/api/app/api/v1/access_grants.py) and the admin user list
 * (apps/api/app/api/v1/users.py) needed to populate the grant picker. Only
 * `list` is exposed for users here — creating/editing users themselves is
 * out of this phase's scope (CLAUDE.md §32 style discipline: this feature
 * exists to grant/revoke instance access, not to be a full user-admin
 * console). */

const LIST_ALL_LIMIT = 500

export const usersApi = {
  list: () => apiGet<Page<UserSummary>>('/api/v1/users', { limit: LIST_ALL_LIMIT }),
}

export const accessGrantsApi = {
  listForTeam: (teamId: string) =>
    apiGet<TeamAccessGrant[]>(`/api/v1/teams/${teamId}/access-grants`),
  grantTeam: (teamId: string, userId: string) =>
    apiPost<TeamAccessGrant>(`/api/v1/teams/${teamId}/access-grants`, {
      user_id: userId,
    }),
  revokeTeam: (teamId: string, userId: string) =>
    apiDelete(`/api/v1/teams/${teamId}/access-grants/${userId}`),

  listForProject: (projectId: string) =>
    apiGet<ProjectAccessGrant[]>(`/api/v1/projects/${projectId}/access-grants`),
  grantProject: (projectId: string, userId: string) =>
    apiPost<ProjectAccessGrant>(`/api/v1/projects/${projectId}/access-grants`, {
      user_id: userId,
    }),
  revokeProject: (projectId: string, userId: string) =>
    apiDelete(`/api/v1/projects/${projectId}/access-grants/${userId}`),
}

import { apiGet, apiPatch, apiPost } from '@/api/client'
import type { Page } from '@/types/entities'
import type { UserAccount, UserStatus } from '../types/users'

/** Thin typed wrappers over apps/api's Phase 10/12/15 user-account
 * endpoints (apps/api/app/api/v1/users.py). These are gated by
 * Permission.USER_READ / USER_WRITE (Admin/Owner) and are deliberately
 * NOT organization-scoped — `GET /users` is a global account directory
 * (ADR 0012 Decision 8), `PATCH /users/{id}` resolves the account
 * globally. The only organization-scoped element is the optional
 * `person_id` link, which apps/api validates against the acting
 * organization's People. This module adds no client-side authorization
 * or scoping — it surfaces the backend's 403/404/409/422 verbatim
 * (Phase 29). */

const LIST_ALL_LIMIT = 500

export interface CreateUserInput {
  email: string
  password: string
  display_name: string
  person_id?: string | null
}

/** Phase 34: `q` is a case-insensitive substring match against email OR
 * display_name; `status` is an exact match — both applied server-side by
 * apps/api (GET /api/v1/users?q=&status=), never filtered client-side over
 * an already-fetched page. Neither narrows the directory's existing global
 * (cross-organization) scope. */
export interface UserAccountFilters {
  q?: string
  status?: UserStatus
}

export const usersApi = {
  list: (filters: UserAccountFilters = {}) =>
    apiGet<Page<UserAccount>>('/api/v1/users', {
      limit: LIST_ALL_LIMIT,
      q: filters.q || undefined,
      status: filters.status || undefined,
    }),

  create: (data: CreateUserInput) => apiPost<UserAccount>('/api/v1/users', data),

  /** Only `active` / `disabled` are ever sent — a disable routes through
   * apps/api's Phase 15 last-owner guard (422 if it would strand an
   * organization without an active Owner); `active` re-enables a
   * `disabled` or `invited` account. */
  setStatus: (userId: string, status: 'active' | 'disabled') =>
    apiPatch<UserAccount>(`/api/v1/users/${userId}`, { status }),
}

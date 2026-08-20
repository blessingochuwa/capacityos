import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { setUnauthorizedHandler } from '@/api/client'
import { authApi, type LoginInput } from '../api/authApi'
import type { CurrentUser } from '../types/auth'

export const SESSION_QUERY_KEY = ['session'] as const

/** Phase 12: 'no-organization' is distinct from 'authenticated' — the
 * session is valid but no organization is currently selected (0 or many
 * memberships at login, before an explicit switch-organization call, or
 * after the active organization/membership was revoked and the next
 * request re-verified that — see get_current_membership's docstring in
 * apps/api/app/api/deps.py). RequireAuth reacts to this by redirecting to
 * /select-organization rather than rendering the protected app shell. */
export type AuthStatus =
  | 'loading'
  | 'authenticated'
  | 'unauthenticated'
  | 'no-organization'

interface AuthContextValue {
  user: CurrentUser | null
  status: AuthStatus
  /** UX-only gating — the backend re-checks every permission independently
   * and remains the real security boundary (CLAUDE.md §21). Never throws
   * and never requires a provider: outside of AuthProvider (e.g. an
   * isolated component test with no session context) this safely denies
   * everything rather than crashing or defaulting to "allowed." */
  can: (permission: string) => boolean
  /** Phase 11: does the current user hold write/delete authority on THIS
   * specific team/project instance? Owner/Admin are always true (their
   * bypass is role-based, not grant-based, matching the backend's
   * has_permission — see docs/adr/0011-instance-level-resource-authorization.md).
   * Everyone else needs BOTH the underlying type-level permission (via
   * `can`) AND the resource id present in their accessible-ids list — this
   * mirrors the backend's two-layer check so the UI never shows an
   * affordance the API would actually reject. Still UX-only: the backend
   * re-checks independently on every request regardless of what this
   * returns. */
  canManageResource: (resourceType: 'team' | 'project', resourceId: string) => boolean
  login: (input: LoginInput) => Promise<void>
  logout: () => Promise<void>
  /** Phase 12 — re-verified server-side (see authApi.switchOrganization);
   * the cache-purge here mirrors logout's exactly (see switchOrganization
   * mutation below for why threading organizationId into every query key
   * instead was deliberately rejected). */
  switchOrganization: (organizationId: string) => Promise<void>
}

const DEFAULT_CONTEXT: AuthContextValue = {
  user: null,
  status: 'unauthenticated',
  can: () => false,
  canManageResource: () => false,
  login: async () => {
    throw new Error('AuthProvider is not mounted.')
  },
  logout: async () => {
    throw new Error('AuthProvider is not mounted.')
  },
  switchOrganization: async () => {
    throw new Error('AuthProvider is not mounted.')
  },
}

const AuthContext = createContext<AuthContextValue>(DEFAULT_CONTEXT)

export function useAuth(): AuthContextValue {
  return useContext(AuthContext)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  const sessionQuery = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: authApi.me,
    retry: false,
    staleTime: Infinity,
  })

  useEffect(() => {
    // Clearing the cached session is enough — RequireAuth (below) reacts to
    // `status` flipping to 'unauthenticated' and declaratively redirects
    // to /login via <Navigate>, so no imperative navigation is needed here
    // (and this module deliberately never imports the router, to avoid a
    // AuthContext <-> routes.tsx <-> RequireAuth import cycle).
    setUnauthorizedHandler(() => {
      queryClient.setQueryData(SESSION_QUERY_KEY, null)
    })
    return () => setUnauthorizedHandler(null)
  }, [queryClient])

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: (user) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, user)
    },
  })

  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.setQueryData(SESSION_QUERY_KEY, null)
      // Every other cached query may hold data scoped to the session that
      // just ended — clearing avoids a moment where a subsequent login (as
      // a different user) briefly renders stale, previous-session data.
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== 'session',
      })
    },
  })

  const switchOrganizationMutation = useMutation({
    mutationFn: authApi.switchOrganization,
    onSuccess: (user) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, user)
      // Every cached query may hold data scoped to the PREVIOUS active
      // organization — reusing logout's exact purge here (rather than
      // threading organizationId into every one of this app's ~27 query
      // keys) is a deliberate choice: it costs a few lines instead of a
      // call-site change everywhere a query key is defined, and a stale
      // cache entry for one extra render is a UX glitch, never a leak,
      // since the backend re-scopes every request to the NEW active
      // organization regardless of what's cached client-side (CLAUDE.md
      // §21). See docs/adr/0012-organizations-multi-tenancy.md.
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== 'session',
      })
    },
  })

  const user = sessionQuery.data ?? null
  const status: AuthStatus = sessionQuery.isLoading
    ? 'loading'
    : !user
      ? 'unauthenticated'
      : user.active_organization
        ? 'authenticated'
        : 'no-organization'

  const can = (permission: string): boolean => user?.permissions.includes(permission) ?? false

  const canManageResource = (resourceType: 'team' | 'project', resourceId: string): boolean => {
    if (!user) return false
    if (user.role === 'owner' || user.role === 'admin') return true
    const permission = resourceType === 'team' ? 'team.write' : 'project.write'
    if (!can(permission)) return false
    const accessibleIds =
      resourceType === 'team' ? user.accessible_team_ids : user.accessible_project_ids
    return accessibleIds.includes(resourceId)
  }

  const value: AuthContextValue = {
    user,
    status,
    can,
    canManageResource,
    login: async (input) => {
      await loginMutation.mutateAsync(input)
    },
    logout: async () => {
      await logoutMutation.mutateAsync()
    },
    switchOrganization: async (organizationId) => {
      await switchOrganizationMutation.mutateAsync(organizationId)
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

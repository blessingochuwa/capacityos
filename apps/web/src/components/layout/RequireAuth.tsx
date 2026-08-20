import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { LoadingState } from '@/components/ui/Skeleton'
import { useAuth } from '@/features/auth/context/AuthContext'

/** Wraps the protected route tree (see app/routes.tsx) — redirects to
 * /login when there's no session, preserving the originally-requested path
 * via location state so LoginPage can send the user back after a
 * successful login. Phase 12: also redirects to /select-organization when
 * the session is valid but no organization is currently active (see
 * AuthContext's 'no-organization' status) — the protected app shell needs
 * an active organization to render anything meaningful. The backend
 * remains the real security boundary (CLAUDE.md §21): this only prevents a
 * flash of protected UI, it does not make any API call itself trustworthy
 * on its own. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return <LoadingState label="Checking your session…" />
  }
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  if (status === 'no-organization') {
    return <Navigate to="/select-organization" replace state={{ from: location }} />
  }
  return <>{children}</>
}

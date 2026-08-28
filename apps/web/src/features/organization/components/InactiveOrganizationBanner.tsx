import { Link } from 'react-router-dom'
import { useAuth } from '@/features/auth/context/AuthContext'

/**
 * A persistent, shell-level notice shown whenever the caller's *active*
 * organization has been deactivated (`active_organization.is_active ===
 * false`, straight from `/auth/me` — Phase 33). It is not a modal and not
 * a dismissible toast: it stays until the organization is active again.
 *
 * Recovery routing is unchanged — an Owner is pointed at the existing
 * Phase 32 `/admin/organization` recovery panel, which is the only place
 * `POST /api/v1/organizations/{id}/reactivate` is called. A non-Owner
 * gets no action they cannot perform (CLAUDE.md §21 — the banner is UX,
 * never an authorization boundary; the backend re-checks everything).
 */
export function InactiveOrganizationBanner() {
  const { user, can } = useAuth()

  if (user?.active_organization?.is_active !== false) {
    return null
  }

  const canRecover = can('organization.manage')

  return (
    <div
      role="alert"
      className="border-b border-amber-800 bg-amber-950 px-4 py-2.5 text-sm text-amber-200 sm:px-6"
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-medium">This organization is inactive.</span>
        <span className="text-amber-300/90">
          {user.active_organization.name} has been deactivated, so its people, projects,
          and plans are unavailable right now.
        </span>
        {canRecover ? (
          <Link
            to="/admin/organization"
            className="font-medium text-amber-100 underline underline-offset-2 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300"
          >
            Go to organization settings to reactivate it
          </Link>
        ) : (
          <span className="text-amber-300/90">
            Ask an organization Owner to reactivate it.
          </span>
        )}
      </div>
    </div>
  )
}

import { useState } from 'react'
import { Button } from '@/components/ui/Button'

interface DeactivateOrganizationSectionProps {
  organizationName: string
  /** Fires only after the two-step inline confirmation. */
  onConfirm: () => void
  isPending: boolean
  /** The backend's own message when the mutation failed — in particular
   * the 422 raised by the >= 2-active-Owner safety guard, shown verbatim
   * (Phase 32 never re-derives that rule client-side). */
  error?: string
}

/**
 * The "danger" part of Organization Settings. Rendered only inside the
 * already-Owner-gated OrganizationSettingsPage, so it needs no permission
 * check of its own — the backend re-checks `ORGANIZATION_MANAGE` + CSRF on
 * every call regardless (CLAUDE.md §21).
 *
 * Uses the established two-step inline-confirm pattern
 * (ScenarioWorkspacePage / features/users' UsersTable) — no modal, no new
 * primitive.
 */
export function DeactivateOrganizationSection({
  organizationName,
  onConfirm,
  isPending,
  error,
}: DeactivateOrganizationSectionProps) {
  const [confirming, setConfirming] = useState(false)

  return (
    <div className="space-y-2 border-t border-slate-800 pt-6">
      <p className="text-xs font-medium text-slate-400">Deactivation</p>
      <p className="max-w-prose text-sm text-slate-400">
        Deactivating <span className="text-slate-200">{organizationName}</span> makes it
        immediately inactive: its people, projects, and plans stop being accessible for
        everyone until it is reactivated. Nothing is deleted — memberships and data are
        kept exactly as they are. Only an Owner can reactivate it afterwards, and the
        backend allows deactivation only while another active Owner remains who could do
        so.
      </p>

      {confirming ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400">
            Deactivate {organizationName}?
          </span>
          <Button
            variant="secondary"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? 'Deactivating…' : 'Confirm deactivate'}
          </Button>
          <Button
            variant="ghost"
            onClick={() => setConfirming(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
        </div>
      ) : (
        <Button variant="ghost" onClick={() => setConfirming(true)}>
          Deactivate organization
        </Button>
      )}

      {error ? (
        <p role="alert" className="text-xs text-rose-300">
          {error}
        </p>
      ) : null}
    </div>
  )
}

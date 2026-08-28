import { useState } from 'react'
import { ApiError } from '@/api/client'
import { Select } from '@/components/ui/Select'
import { useAuth } from '../context/AuthContext'

/** Phase 12 — data comes entirely from `user.organizations` (already loaded
 * by /auth/me), so unlike TeamPicker/ProjectSwitcher this needs no fetch of
 * its own and no loading/error state. Switching goes through
 * AuthContext.switchOrganization, never local state, so the cache-purge
 * that mutation performs always fires.
 *
 * Phase 33 — a deactivated organization can't be switched into
 * (`POST /auth/switch-organization` 404s on it), so it is no longer
 * offered as a normal choice: `options` is the caller's ACTIVE
 * organizations, plus the current one even if it happens to be inactive
 * (so the `<Select>`'s value always has a matching option and the user
 * can still see which org they're in). Renders nothing when that leaves
 * one option or fewer — there is nothing to switch to. */
export function OrganizationSwitcher() {
  const { user, switchOrganization } = useAuth()
  const [isSwitching, setIsSwitching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!user) {
    return null
  }

  const activeOrgId = user.active_organization?.id
  const selectable = user.organizations.filter(
    (org) => org.is_active || org.id === activeOrgId,
  )

  if (selectable.length <= 1) {
    return null
  }

  async function handleChange(organizationId: string) {
    setError(null)
    setIsSwitching(true)
    try {
      await switchOrganization(organizationId)
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Could not switch organizations. Please try again.',
      )
    } finally {
      setIsSwitching(false)
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <Select
        label="Organization"
        value={activeOrgId ?? ''}
        disabled={isSwitching}
        options={selectable.map((org) => ({
          value: org.id,
          label: org.is_active ? org.name : `${org.name} (inactive)`,
        }))}
        onChange={(event) => void handleChange(event.target.value)}
      />
      {error ? (
        <p role="alert" className="text-xs text-rose-300">
          {error}
        </p>
      ) : null}
    </div>
  )
}

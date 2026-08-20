import { useState } from 'react'
import { ApiError } from '@/api/client'
import { Select } from '@/components/ui/Select'
import { useAuth } from '../context/AuthContext'

/** Phase 12 — data comes entirely from `user.organizations` (already loaded
 * by /auth/me), so unlike TeamPicker/ProjectSwitcher this needs no fetch of
 * its own and no loading/error state. Switching goes through
 * AuthContext.switchOrganization, never local state, so the cache-purge
 * that mutation performs always fires. Renders nothing for a user with
 * only one organization — there is nothing to switch to. */
export function OrganizationSwitcher() {
  const { user, switchOrganization } = useAuth()
  const [isSwitching, setIsSwitching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!user || user.organizations.length <= 1) {
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
        value={user.active_organization?.id ?? ''}
        disabled={isSwitching}
        options={user.organizations.map((org) => ({ value: org.id, label: org.name }))}
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

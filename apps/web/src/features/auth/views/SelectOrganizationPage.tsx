import { useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { organizationsApi } from '../api/organizationsApi'
import { useAuth } from '../context/AuthContext'

interface LocationState {
  from?: { pathname: string }
}

/** Shown when AuthContext's status is 'no-organization' (Phase 12) — the
 * session is valid but nothing is currently selected: either the account
 * belongs to zero or several organizations (login only auto-selects when
 * there's exactly one), or the previously-active membership/organization
 * was revoked/deactivated and the next request caught it. Lists every
 * organization the account currently belongs to plus a minimal create-org
 * form — the only way into the app for a genuinely new account with no
 * memberships anywhere. See docs/adr/0012-organizations-multi-tenancy.md. */
export function SelectOrganizationPage() {
  const { status, user, switchOrganization } = useAuth()
  const location = useLocation()
  const [switchingId, setSwitchingId] = useState<string | null>(null)
  const [switchError, setSwitchError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  if (status === 'authenticated') {
    const from = (location.state as LocationState | null)?.from?.pathname ?? '/'
    return <Navigate to={from} replace />
  }

  async function handleSelect(organizationId: string) {
    setSwitchError(null)
    setSwitchingId(organizationId)
    try {
      await switchOrganization(organizationId)
    } catch (caught) {
      setSwitchError(
        caught instanceof ApiError
          ? caught.message
          : 'Could not switch organizations. Please try again.',
      )
    } finally {
      setSwitchingId(null)
    }
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setCreateError(null)
    setIsCreating(true)
    try {
      const organization = await organizationsApi.create({ name, slug })
      await switchOrganization(organization.id)
    } catch (caught) {
      setCreateError(
        caught instanceof ApiError
          ? caught.message
          : 'Could not create the organization. Please try again.',
      )
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-sm space-y-6">
        <p className="text-center text-sm font-semibold tracking-tight text-slate-100">
          CapacityOS
        </p>

        {user && user.organizations.length > 0 ? (
          <Card>
            <CardHeader
              title="Select an organization"
              description="Choose which organization to work in."
            />
            <CardBody>
              <ul className="space-y-2">
                {user.organizations.map((organization) => (
                  <li key={organization.id}>
                    <Button
                      type="button"
                      variant="secondary"
                      className="w-full justify-start"
                      disabled={switchingId !== null}
                      onClick={() => void handleSelect(organization.id)}
                    >
                      {switchingId === organization.id ? 'Switching…' : organization.name}
                    </Button>
                  </li>
                ))}
              </ul>
              {switchError ? (
                <p role="alert" className="mt-3 text-xs text-rose-300">
                  {switchError}
                </p>
              ) : null}
            </CardBody>
          </Card>
        ) : null}

        <Card>
          <CardHeader
            title="Create an organization"
            description="Start a new organization — you'll be its Owner."
          />
          <CardBody>
            <form onSubmit={(event) => void handleCreate(event)} className="space-y-4">
              <div className="flex flex-col gap-1">
                <label
                  htmlFor="org-name"
                  className="text-xs font-medium text-slate-400"
                >
                  Name
                </label>
                <input
                  id="org-name"
                  type="text"
                  required
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label
                  htmlFor="org-slug"
                  className="text-xs font-medium text-slate-400"
                >
                  Slug
                </label>
                <input
                  id="org-slug"
                  type="text"
                  required
                  pattern="[a-z0-9]+(-[a-z0-9]+)*"
                  placeholder="acme-inc"
                  value={slug}
                  onChange={(event) => setSlug(event.target.value)}
                  className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
                />
              </div>
              {createError ? (
                <p role="alert" className="text-xs text-rose-300">
                  {createError}
                </p>
              ) : null}
              <Button
                type="submit"
                variant="primary"
                className="w-full"
                disabled={isCreating || !name || !slug}
              >
                {isCreating ? 'Creating…' : 'Create organization'}
              </Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

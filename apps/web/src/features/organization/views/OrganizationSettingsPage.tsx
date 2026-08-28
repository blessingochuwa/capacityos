import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/Badge'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { RenameOrganizationForm } from '../components/RenameOrganizationForm'
import { useOrganization, useRenameOrganization } from '../hooks/useOrganization'

/**
 * "Can I safely understand and manage the current organization's
 * settings?" — the current organization's name, its immutable slug, and
 * its status, plus a rename action over the existing Phase 12
 * `PATCH /api/v1/organizations/{id}` endpoint.
 *
 * Gated by `can('organization.manage')` for UX only — that permission is
 * Owner-only (`ROLE_PERMISSIONS`), and the backend re-checks it plus the
 * active-organization match on every request (a path id that isn't the
 * caller's active org 404s). This page re-derives none of that and
 * surfaces the backend's own 403/404/422 inline. Mirrors
 * features/members/ and features/users/ one-for-one.
 *
 * Organization deactivation is deliberately NOT offered here: the backend
 * `POST .../{id}/deactivate` is irreversible through the product (no
 * reactivation path exists) and denies every member — including the
 * acting Owner — on their next request, with no backend guard. Exposing
 * it was deferred. See docs/adr/0030-organization-settings-ui.md.
 */
export function OrganizationSettingsPage() {
  const { user, can } = useAuth()

  if (!can('organization.manage')) {
    return (
      <div className="space-y-6">
        <PageHeader title="Organization" />
        <ViewOnlyNotice message="Only an Owner can view or change organization settings." />
      </div>
    )
  }

  const organizationId = user?.active_organization?.id

  return (
    <div className="space-y-6">
      <PageHeader
        title="Organization"
        description="The name, identifier, and status of the organization you are currently working in."
      />

      <Card>
        <CardHeader
          title="Organization settings"
          description="Rename the organization. Its identifier (slug) is fixed once created."
        />
        <CardBody>
          {!organizationId ? (
            <EmptyState title="Select an organization to manage its settings." />
          ) : (
            <OrganizationSettingsManager organizationId={organizationId} />
          )}
        </CardBody>
      </Card>
    </div>
  )
}

function OrganizationSettingsManager({ organizationId }: { organizationId: string }) {
  const organizationQuery = useOrganization(organizationId)
  const rename = useRenameOrganization(organizationId)

  return (
    <QueryBoundary query={organizationQuery} loadingLabel="Loading organization…">
      {(organization) => (
        <dl className="space-y-6">
          <div>
            <dt className="text-xs font-medium text-slate-400">Name</dt>
            <dd className="mt-2">
              <RenameOrganizationForm
                currentName={organization.name}
                onSubmit={(name) => rename.mutateAsync(name)}
                isPending={rename.isPending}
                error={rename.isError ? rename.error.message : undefined}
              />
              {rename.isSuccess && !rename.isPending ? (
                <p className="mt-2 text-xs text-emerald-300">Name updated.</p>
              ) : null}
            </dd>
          </div>

          <div>
            <dt className="text-xs font-medium text-slate-400">Identifier (slug)</dt>
            <dd className="mt-1 flex items-center gap-2 text-sm text-slate-200">
              <code className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-300">
                {organization.slug}
              </code>
              <span className="text-xs text-slate-500">Cannot be changed</span>
            </dd>
          </div>

          <div>
            <dt className="text-xs font-medium text-slate-400">Status</dt>
            <dd className="mt-1">
              <Badge variant={organization.is_active ? 'success' : 'neutral'}>
                {organization.is_active ? 'Active' : 'Inactive'}
              </Badge>
            </dd>
          </div>
        </dl>
      )}
    </QueryBoundary>
  )
}

import { ApiError } from '@/api/client'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/Badge'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { DeactivateOrganizationSection } from '../components/DeactivateOrganizationSection'
import { InactiveOrganizationPanel } from '../components/InactiveOrganizationPanel'
import { RenameOrganizationForm } from '../components/RenameOrganizationForm'
import {
  useDeactivateOrganization,
  useOrganization,
  useReactivateOrganization,
  useRenameOrganization,
} from '../hooks/useOrganization'

/**
 * "Can I safely understand and manage the current organization's
 * settings?" — the current organization's name, its immutable slug, its
 * status, rename (Phase 30), and the deactivation/reactivation lifecycle
 * built on the Phase 31 backend contract (Phase 32).
 *
 * Gated by `can('organization.manage')` for UX only — Owner-only
 * (`ROLE_PERMISSIONS`). The backend re-checks it, the active-organization
 * match, CSRF, and the >= 2-active-Owner deactivation guard on every
 * request (CLAUDE.md §21); this page re-derives none of it and surfaces
 * the backend's own 403/404/409/422 verbatim.
 *
 * When the current organization has been deactivated, `GET
 * /api/v1/organizations/{id}` returns the Phase 12/31 409; this page
 * detects that and renders InactiveOrganizationPanel (the recovery
 * surface) in place of the settings form. It never re-interprets a 409
 * anywhere else in the app.
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
  const organizationName = user?.active_organization?.name ?? 'this organization'

  return (
    <div className="space-y-6">
      <PageHeader
        title="Organization"
        description="The name, identifier, and status of the organization you are currently working in."
      />

      <Card>
        <CardHeader
          title="Organization settings"
          description="Rename the organization, or deactivate it. Its identifier (slug) is fixed once created."
        />
        <CardBody>
          {!organizationId ? (
            <EmptyState title="Select an organization to manage its settings." />
          ) : (
            <OrganizationSettingsManager
              organizationId={organizationId}
              organizationName={organizationName}
            />
          )}
        </CardBody>
      </Card>
    </div>
  )
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Something went wrong. Please try again.'
}

function OrganizationSettingsManager({
  organizationId,
  organizationName,
}: {
  organizationId: string
  organizationName: string
}) {
  const organizationQuery = useOrganization(organizationId)
  const rename = useRenameOrganization(organizationId)
  const deactivate = useDeactivateOrganization(organizationId)
  const reactivate = useReactivateOrganization(organizationId)

  const isDeactivatedOrgError =
    organizationQuery.isError &&
    organizationQuery.error instanceof ApiError &&
    organizationQuery.error.status === 409

  if (isDeactivatedOrgError) {
    return (
      <InactiveOrganizationPanel
        organizationName={organizationName}
        onReactivate={() => reactivate.mutate()}
        isPending={reactivate.isPending}
        error={reactivate.isError ? errorMessage(reactivate.error) : undefined}
      />
    )
  }

  return (
    <QueryBoundary query={organizationQuery} loadingLabel="Loading organization…">
      {(organization) => (
        <div className="space-y-8">
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

          <DeactivateOrganizationSection
            organizationName={organization.name}
            onConfirm={() => deactivate.mutate()}
            isPending={deactivate.isPending}
            error={deactivate.isError ? errorMessage(deactivate.error) : undefined}
          />
        </div>
      )}
    </QueryBoundary>
  )
}

import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'

interface InactiveOrganizationPanelProps {
  organizationName: string
  /** Calls the Phase 31 reactivation endpoint. */
  onReactivate: () => void
  isPending: boolean
  /** The backend's own message on failure (403 for a non-Owner, 404 for a
   * non-member, etc.), shown verbatim. */
  error?: string
}

/**
 * The recovery surface for a deactivated organization. Reached only when
 * OrganizationSettingsPage is already Owner-gated AND `GET
 * /api/v1/organizations/{id}` returned the Phase 12/31 409
 * ("no longer active") — which, for a caller who still holds
 * `organization.manage`, unambiguously means the organization was
 * deactivated (a revoked membership would instead null out the caller's
 * role/permissions and never reach this component).
 *
 * Reactivation is Owner-only on the backend; this component performs no
 * check of its own and surfaces the backend's 403/404 verbatim. On
 * success the mutation revalidates every query, so this panel simply
 * unmounts as `GET /organizations/{id}` starts returning 200 again — no
 * re-login, matching Phase 31's verified behavior.
 */
export function InactiveOrganizationPanel({
  organizationName,
  onReactivate,
  isPending,
  error,
}: InactiveOrganizationPanelProps) {
  return (
    <Card>
      <CardHeader
        title="This organization is inactive"
        description={`${organizationName} has been deactivated.`}
      />
      <CardBody className="space-y-4">
        <p className="max-w-prose text-sm text-slate-400">
          While it is inactive, no one can reach its people, projects, or plans, and
          normal pages will report that the organization is no longer active.
          Reactivating restores access for everyone immediately — memberships and data
          were never removed. You will not need to sign in again.
        </p>
        <Button variant="primary" onClick={onReactivate} disabled={isPending}>
          {isPending ? 'Reactivating…' : 'Reactivate organization'}
        </Button>
        {error ? (
          <p role="alert" className="text-xs text-rose-300">
            {error}
          </p>
        ) : null}
      </CardBody>
    </Card>
  )
}

import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { AddMemberForm } from '../components/AddMemberForm'
import { MembersTable } from '../components/MembersTable'
import {
  useAddMember,
  useChangeMemberRole,
  useMemberships,
  useReactivateMember,
  useRevokeMember,
} from '../hooks/useMemberships'

/**
 * "Who is in this organization, and what can they do?" (CLAUDE.md §16/§27)
 * — the first frontend surface for the Phase 12/15 membership-management
 * API. Lists every membership (active and revoked), changes a member's
 * role, revokes and reactivates a membership, and adds an existing account
 * by email.
 *
 * Everything shown here is gated by `can('membership.manage')` for UX only
 * — the backend (Permission.MEMBERSHIP_MANAGE, the Owner-escalation rule,
 * the Phase 15 last-Owner invariant, and the Phase 12 active-organization
 * boundary) is the security boundary and re-checks every request
 * independently (CLAUDE.md §21). This page never re-derives any of that;
 * it surfaces the backend's own 403/422/404/409 message inline. Mirrors
 * features/access/views/AccessManagementPage's shape exactly.
 */
export function MembersPage() {
  const { user, can } = useAuth()

  if (!can('membership.manage')) {
    return (
      <div className="space-y-6">
        <PageHeader title="Members" />
        <ViewOnlyNotice message="Your role doesn't include permission to manage this organization's members." />
      </div>
    )
  }

  const organizationId = user?.active_organization?.id

  return (
    <div className="space-y-6">
      <PageHeader
        title="Members"
        description="Everyone with a membership in this organization, their role, and their status. Adding a member requires an existing CapacityOS account — no account is created here."
      />

      <Card>
        <CardHeader
          title="Organization members"
          description="Change a member's role, revoke a membership, or reactivate a revoked one. An organization always keeps at least one active Owner."
        />
        <CardBody className="space-y-4">
          {!organizationId ? (
            <EmptyState title="Select an organization to manage its members." />
          ) : (
            <MembersManager organizationId={organizationId} />
          )}
        </CardBody>
      </Card>
    </div>
  )
}

function MembersManager({ organizationId }: { organizationId: string }) {
  const membershipsQuery = useMemberships(organizationId)
  const addMember = useAddMember(organizationId)
  const changeRole = useChangeMemberRole(organizationId)
  const revokeMember = useRevokeMember(organizationId)
  const reactivateMember = useReactivateMember(organizationId)

  const pendingUserId = changeRole.isPending
    ? changeRole.variables?.userId
    : revokeMember.isPending
      ? (revokeMember.variables as string | undefined)
      : reactivateMember.isPending
        ? (reactivateMember.variables as string | undefined)
        : undefined

  const actionError: { userId: string; message: string } | undefined =
    changeRole.isError && changeRole.variables
      ? { userId: changeRole.variables.userId, message: changeRole.error.message }
      : revokeMember.isError && typeof revokeMember.variables === 'string'
        ? { userId: revokeMember.variables, message: revokeMember.error.message }
        : reactivateMember.isError && typeof reactivateMember.variables === 'string'
          ? {
              userId: reactivateMember.variables,
              message: reactivateMember.error.message,
            }
          : undefined

  return (
    <div className="space-y-4">
      <AddMemberForm
        onSubmit={(email, role) => addMember.mutateAsync({ email, role })}
        isPending={addMember.isPending}
        error={addMember.isError ? addMember.error.message : undefined}
      />
      <QueryBoundary query={membershipsQuery} loadingLabel="Loading members…">
        {(page) => (
          <MembersTable
            memberships={page.items}
            onRoleChange={(userId, role) => changeRole.mutate({ userId, role })}
            onRevoke={(userId) => revokeMember.mutate(userId)}
            onReactivate={(userId) => reactivateMember.mutate(userId)}
            pendingUserId={pendingUserId}
            actionError={actionError}
          />
        )}
      </QueryBoundary>
    </div>
  )
}

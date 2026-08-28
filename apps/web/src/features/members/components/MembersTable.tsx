import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import type { UserRole } from '@/features/auth/types/auth'
import { ROLE_OPTIONS } from '../constants'
import type { Membership } from '../types/members'

interface MembersTableProps {
  memberships: Membership[]
  onRoleChange: (userId: string, role: UserRole) => void
  onRevoke: (userId: string) => void
  onReactivate: (userId: string) => void
  /** The one member row whose mutation is currently in flight — its
   * controls are disabled until it settles. */
  pendingUserId?: string
  /** The most recent failed action, keyed to the member it was for, so the
   * backend's own message (e.g. "Only an Owner can grant or change an
   * Owner/Admin role", "Cannot demote the last remaining Owner") is shown
   * on the exact row it applies to. */
  actionError?: { userId: string; message: string }
}

const SELECT_CLASS =
  'w-32 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 disabled:cursor-not-allowed disabled:opacity-50'

export function MembersTable({
  memberships,
  onRoleChange,
  onRevoke,
  onReactivate,
  pendingUserId,
  actionError,
}: MembersTableProps) {
  if (memberships.length === 0) {
    return (
      <EmptyState
        title="This organization has no members yet."
        description="Add an existing account by email above."
      />
    )
  }

  return (
    <Table caption="Members of this organization, their role, and their status">
      <thead>
        <tr>
          <Th scope="col">Member</Th>
          <Th scope="col">Role</Th>
          <Th scope="col">Status</Th>
          <Th scope="col">
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {memberships.map((member) => {
          const isPending = pendingUserId === member.user_id
          const rowError =
            actionError?.userId === member.user_id ? actionError.message : null
          return (
            <tr key={member.user_id}>
              <Td className="font-medium text-slate-100">
                {member.display_name}
                <span className="block text-xs font-normal text-slate-400">
                  {member.email}
                </span>
                {rowError ? (
                  <span role="alert" className="mt-1 block text-xs text-rose-300">
                    {rowError}
                  </span>
                ) : null}
              </Td>
              <Td>
                <select
                  aria-label={`Role for ${member.display_name}`}
                  value={member.role}
                  disabled={isPending || member.status === 'revoked'}
                  onChange={(event) =>
                    onRoleChange(member.user_id, event.target.value as UserRole)
                  }
                  className={SELECT_CLASS}
                >
                  {ROLE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Td>
              <Td>
                <Badge variant={member.status === 'active' ? 'success' : 'neutral'}>
                  {member.status === 'active' ? 'Active' : 'Revoked'}
                </Badge>
              </Td>
              <Td>
                {member.status === 'active' ? (
                  <Button
                    variant="ghost"
                    onClick={() => onRevoke(member.user_id)}
                    disabled={isPending}
                  >
                    {isPending ? 'Revoking…' : 'Revoke'}
                  </Button>
                ) : (
                  <Button
                    variant="ghost"
                    onClick={() => onReactivate(member.user_id)}
                    disabled={isPending}
                  >
                    {isPending ? 'Reactivating…' : 'Reactivate'}
                  </Button>
                )}
              </Td>
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}

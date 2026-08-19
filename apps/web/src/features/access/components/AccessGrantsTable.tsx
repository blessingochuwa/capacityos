import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import type { UserSummary } from '../types/access'

interface GrantRow {
  user_id: string
  granted_by_user_id: string | null
  created_at: string
}

interface AccessGrantsTableProps {
  caption: string
  grants: GrantRow[]
  users: UserSummary[]
  onRevoke: (userId: string) => void
  revokingUserId?: string
}

function labelFor(users: UserSummary[], userId: string | null): string {
  if (!userId) return '—'
  const user = users.find((candidate) => candidate.id === userId)
  return user ? `${user.display_name} (${user.email})` : userId
}

export function AccessGrantsTable({
  caption,
  grants,
  users,
  onRevoke,
  revokingUserId,
}: AccessGrantsTableProps) {
  if (grants.length === 0) {
    return (
      <EmptyState
        title="No one has explicit access yet."
        description="Grant access above so a Manager can create, edit, or delete this resource."
      />
    )
  }

  return (
    <Table caption={caption}>
      <thead>
        <tr>
          <Th scope="col">User</Th>
          <Th scope="col">Granted by</Th>
          <Th scope="col">Granted at</Th>
          <Th scope="col">
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {grants.map((grant) => (
          <tr key={grant.user_id}>
            <Td className="font-medium text-slate-100">{labelFor(users, grant.user_id)}</Td>
            <Td>{labelFor(users, grant.granted_by_user_id)}</Td>
            <Td>{new Date(grant.created_at).toLocaleString()}</Td>
            <Td>
              <Button
                variant="ghost"
                onClick={() => onRevoke(grant.user_id)}
                disabled={revokingUserId === grant.user_id}
              >
                {revokingUserId === grant.user_id ? 'Revoking…' : 'Revoke'}
              </Button>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

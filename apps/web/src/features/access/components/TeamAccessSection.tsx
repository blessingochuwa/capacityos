import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { TeamPicker } from '@/features/capacity/components/TeamPicker'
import { AccessGrantsTable } from './AccessGrantsTable'
import { UserPicker } from './UserPicker'
import { useUsers } from '../hooks/useUsers'
import {
  useGrantTeamAccess,
  useRevokeTeamAccess,
  useTeamAccessGrants,
} from '../hooks/useTeamAccessGrants'

export function TeamAccessSection() {
  const [teamId, setTeamId] = useState<string | undefined>(undefined)
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>(undefined)
  const usersQuery = useUsers()
  const grantsQuery = useTeamAccessGrants(teamId)
  const grantAccess = useGrantTeamAccess(teamId ?? '')
  const revokeAccess = useRevokeTeamAccess(teamId ?? '')

  function handleGrant() {
    if (!teamId || !selectedUserId) return
    grantAccess.mutate(selectedUserId, {
      onSuccess: () => setSelectedUserId(undefined),
    })
  }

  return (
    <div className="space-y-4">
      <div className="w-64">
        <TeamPicker value={teamId} onChange={setTeamId} />
      </div>

      {!teamId ? (
        <EmptyState title="Select a team to manage who can edit it." />
      ) : (
        <QueryBoundary query={grantsQuery} loadingLabel="Loading access grants…">
          {(grants) => (
            <div className="space-y-4">
              <div className="flex flex-wrap items-end gap-3">
                <div className="w-72">
                  <UserPicker
                    value={selectedUserId}
                    onChange={setSelectedUserId}
                    excludeUserIds={grants.map((g) => g.user_id)}
                  />
                </div>
                <Button
                  variant="primary"
                  onClick={handleGrant}
                  disabled={!selectedUserId || grantAccess.isPending}
                >
                  {grantAccess.isPending ? 'Granting…' : 'Grant access'}
                </Button>
                {grantAccess.isError ? (
                  <p role="alert" className="text-xs text-rose-300">
                    {grantAccess.error.message}
                  </p>
                ) : null}
              </div>
              <AccessGrantsTable
                caption="Users explicitly granted access to this team"
                grants={grants}
                users={usersQuery.data?.items ?? []}
                onRevoke={(userId) => revokeAccess.mutate(userId)}
                revokingUserId={
                  revokeAccess.isPending
                    ? (revokeAccess.variables as string | undefined)
                    : undefined
                }
              />
            </div>
          )}
        </QueryBoundary>
      )}
    </div>
  )
}

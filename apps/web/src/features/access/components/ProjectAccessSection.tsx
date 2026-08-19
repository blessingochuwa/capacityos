import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { ProjectFilterPicker } from '@/features/insights/components/ProjectFilterPicker'
import { AccessGrantsTable } from './AccessGrantsTable'
import { UserPicker } from './UserPicker'
import { useUsers } from '../hooks/useUsers'
import {
  useGrantProjectAccess,
  useProjectAccessGrants,
  useRevokeProjectAccess,
} from '../hooks/useProjectAccessGrants'

export function ProjectAccessSection() {
  const [projectId, setProjectId] = useState<string | undefined>(undefined)
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>(undefined)
  const usersQuery = useUsers()
  const grantsQuery = useProjectAccessGrants(projectId)
  const grantAccess = useGrantProjectAccess(projectId ?? '')
  const revokeAccess = useRevokeProjectAccess(projectId ?? '')

  function handleGrant() {
    if (!projectId || !selectedUserId) return
    grantAccess.mutate(selectedUserId, {
      onSuccess: () => setSelectedUserId(undefined),
    })
  }

  return (
    <div className="space-y-4">
      <div className="w-64">
        <ProjectFilterPicker value={projectId} onChange={setProjectId} />
      </div>

      {!projectId ? (
        <EmptyState title="Select a project to manage who can edit it." />
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
                caption="Users explicitly granted access to this project"
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

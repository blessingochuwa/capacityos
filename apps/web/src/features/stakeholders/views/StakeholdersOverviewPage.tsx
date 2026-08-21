import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { ProjectFilterPicker } from '@/features/insights/components/ProjectFilterPicker'
import { usePeopleLookup } from '@/hooks/usePeople'
import { StakeholderForm } from '../components/StakeholderForm'
import { StakeholdersTable } from '../components/StakeholdersTable'
import { useDeleteStakeholder } from '../hooks/useStakeholderMutations'
import { useStakeholders } from '../hooks/useStakeholders'

/**
 * "Who needs to know, and who decides?" (CLAUDE.md §16/§38) — a project's
 * stakeholder register: role, influence, interest, decision authority, and
 * communication needs. Deliberately NOT integrated into Insights — §16
 * defines no deterministic signal (no threshold, no derived fact to
 * classify), and inventing one would be exactly the "stakeholder score"
 * CLAUDE.md §17's false-precision rule already forbids for Risk. See
 * docs/adr/0014-phase-14-stakeholder-management.md.
 */
export function StakeholdersOverviewPage() {
  const { can } = useAuth()
  const canManageStakeholders = can('stakeholder.write')
  const [searchParams, setSearchParams] = useSearchParams()
  const projectId = searchParams.get('project') ?? undefined
  const [editingId, setEditingId] = useState<string | undefined>(undefined)

  const stakeholdersQuery = useStakeholders(projectId)
  const deleteStakeholder = useDeleteStakeholder(projectId ?? '')
  const peopleLookup = usePeopleLookup()
  const personLabels = useMemo(() => {
    const labels = new Map<string, string>()
    for (const [id, person] of peopleLookup) {
      labels.set(id, person.display_name)
    }
    return labels
  }, [peopleLookup])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Stakeholders"
        description="Who needs to be engaged on a project, how much say they have, and how they want to be kept in the loop."
      />

      <Card>
        <CardHeader
          title="Project stakeholder register"
          description="Every recorded stakeholder for the selected project."
        />
        <CardBody className="space-y-4">
          <div className="w-64">
            <ProjectFilterPicker
              value={projectId}
              onChange={(value) => {
                const next = new URLSearchParams(searchParams)
                if (value) next.set('project', value)
                else next.delete('project')
                setSearchParams(next, { replace: true })
                setEditingId(undefined)
              }}
            />
          </div>

          {!projectId ? (
            <EmptyState title="Select a project to view or record its stakeholders." />
          ) : (
            <QueryBoundary query={stakeholdersQuery} loadingLabel="Loading stakeholders…">
              {(stakeholders) => {
                const editing = stakeholders.find((s) => s.id === editingId)
                return (
                  <div className="space-y-4">
                    <StakeholdersTable
                      stakeholders={stakeholders}
                      personLabels={personLabels}
                      canManage={canManageStakeholders}
                      onEdit={setEditingId}
                      onRemove={(stakeholderId) => deleteStakeholder.mutate(stakeholderId)}
                      editingId={editingId}
                      removingId={
                        deleteStakeholder.isPending
                          ? (deleteStakeholder.variables as string | undefined)
                          : undefined
                      }
                    />
                    {canManageStakeholders ? (
                      <StakeholderForm
                        key={editing?.id ?? 'create'}
                        projectId={projectId}
                        stakeholder={editing}
                        onDone={() => setEditingId(undefined)}
                        onCancel={() => setEditingId(undefined)}
                      />
                    ) : (
                      <ViewOnlyNotice message="Your role can view stakeholders but not create or edit them." />
                    )}
                  </div>
                )
              }}
            </QueryBoundary>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

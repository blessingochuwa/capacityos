import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { ProjectFilterPicker } from '@/features/insights/components/ProjectFilterPicker'
import { usePeopleLookup } from '@/hooks/usePeople'
import { useProjectsLookup } from '@/hooks/useProjects'
import { STAKEHOLDER_REGISTER_PAGE_SIZE } from '../api/stakeholdersApi'
import { OrgStakeholderFilterBar } from '../components/OrgStakeholderFilterBar'
import { OrgStakeholderRegisterTable } from '../components/OrgStakeholderRegisterTable'
import { StakeholderForm } from '../components/StakeholderForm'
import { StakeholdersTable } from '../components/StakeholdersTable'
import { useDeleteStakeholder } from '../hooks/useStakeholderMutations'
import { useOrgStakeholders } from '../hooks/useOrgStakeholders'
import { useStakeholders } from '../hooks/useStakeholders'
import type {
  StakeholderDecisionAuthority,
  StakeholderInfluence,
  StakeholderInterest,
} from '../types/stakeholders'

/**
 * "Who needs to know, and who decides?" (CLAUDE.md §16/§38) — a project's
 * stakeholder register: role, influence, interest, decision authority, and
 * communication needs. Deliberately NOT integrated into Insights — §16
 * defines no deterministic signal (no threshold, no derived fact to
 * classify), and inventing one would be exactly the "stakeholder score"
 * CLAUDE.md §17's false-precision rule already forbids for Risk. See
 * docs/adr/0014-phase-14-stakeholder-management.md.
 *
 * Phase 48 adds the org-wide Stakeholder register below the per-project
 * one — a read-only view of every Stakeholder across every project in the
 * active organization (project/influence/interest/decision-authority
 * filters, real server-side pagination via GET /api/v1/stakeholders),
 * answering what the per-project register cannot: "who are the decision
 * makers and high-influence stakeholders across this whole organization?"
 * See docs/adr/0048-org-wide-stakeholder-register.md.
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

      <Card>
        <CardHeader
          title="Organization-wide stakeholder register"
          description="Every stakeholder recorded across every project in this organization — read-only. Filter by project, influence, interest, or decision authority."
        />
        <CardBody className="space-y-4">
          <OrgStakeholderManager personLabels={personLabels} />
        </CardBody>
      </Card>
    </div>
  )
}

function OrgStakeholderManager({ personLabels }: { personLabels: Map<string, string> }) {
  const [projectFilter, setProjectFilter] = useState<string | undefined>(undefined)
  const [influenceFilter, setInfluenceFilter] = useState<StakeholderInfluence | ''>('')
  const [interestFilter, setInterestFilter] = useState<StakeholderInterest | ''>('')
  const [decisionAuthorityFilter, setDecisionAuthorityFilter] = useState<
    StakeholderDecisionAuthority | ''
  >('')
  const [offset, setOffset] = useState(0)

  const projectsLookup = useProjectsLookup()
  const projectLabels = useMemo(() => {
    const labels = new Map<string, string>()
    for (const [id, project] of projectsLookup) {
      labels.set(id, project.name)
    }
    return labels
  }, [projectsLookup])

  const stakeholdersQuery = useOrgStakeholders({
    project_id: projectFilter,
    influence: influenceFilter || undefined,
    interest: interestFilter || undefined,
    decision_authority: decisionAuthorityFilter || undefined,
    offset,
  })

  /** Every filter change returns to the first page — an offset that was
   * valid for the old result set may be past the end of the new one. */
  function applyFilter<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value)
      setOffset(0)
    }
  }

  const isFiltered = Boolean(
    projectFilter || influenceFilter || interestFilter || decisionAuthorityFilter,
  )
  const total = stakeholdersQuery.data?.total ?? 0
  const hasPrevious = offset > 0
  const hasNext = offset + STAKEHOLDER_REGISTER_PAGE_SIZE < total

  return (
    <div className="space-y-4">
      <OrgStakeholderFilterBar
        projectId={projectFilter}
        onProjectChange={applyFilter(setProjectFilter)}
        influenceValue={influenceFilter}
        onInfluenceChange={applyFilter(setInfluenceFilter)}
        interestValue={interestFilter}
        onInterestChange={applyFilter(setInterestFilter)}
        decisionAuthorityValue={decisionAuthorityFilter}
        onDecisionAuthorityChange={applyFilter(setDecisionAuthorityFilter)}
      />

      <QueryBoundary
        query={stakeholdersQuery}
        loadingLabel="Loading the organization's stakeholders…"
      >
        {(page) => (
          <div className="space-y-3">
            <OrgStakeholderRegisterTable
              stakeholders={page.items}
              projectLabels={projectLabels}
              personLabels={personLabels}
              isFiltered={isFiltered}
            />
            {page.total > 0 ? (
              <div className="flex items-center justify-between gap-4 text-xs text-slate-400">
                <span>
                  Showing {offset + 1}–
                  {Math.min(offset + STAKEHOLDER_REGISTER_PAGE_SIZE, page.total)} of {page.total}{' '}
                  stakeholder{page.total === 1 ? '' : 's'}
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    onClick={() =>
                      setOffset((prev) => Math.max(prev - STAKEHOLDER_REGISTER_PAGE_SIZE, 0))
                    }
                    disabled={!hasPrevious}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => setOffset((prev) => prev + STAKEHOLDER_REGISTER_PAGE_SIZE)}
                    disabled={!hasNext}
                  >
                    Next
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}

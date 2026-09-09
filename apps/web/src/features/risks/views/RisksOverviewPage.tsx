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
import { OrgRiskFilterBar } from '../components/OrgRiskFilterBar'
import { OrgRiskRegisterTable } from '../components/OrgRiskRegisterTable'
import { RiskForm } from '../components/RiskForm'
import { RisksTable } from '../components/RisksTable'
import { RISK_REGISTER_PAGE_SIZE } from '../api/risksApi'
import { useDeleteRisk, useUpdateRisk } from '../hooks/useRiskMutations'
import { useOrgRisks } from '../hooks/useOrgRisks'
import { useRisks } from '../hooks/useRisks'
import type { RiskExposure, RiskStatus } from '../types/risks'

/**
 * "What could go wrong on this project, and who owns following up?"
 * (CLAUDE.md §17/§38) — a project's risk register: description, cause,
 * potential effect, probability/impact (exposure derived server-side, never
 * recomputed here — CLAUDE.md §4), response, owner, status, and review
 * date. High-exposure and overdue-review risks also surface as signals on
 * the existing Insights page (features/insights/) — this page is the "what
 * do we have" register; Insights is the "where should I look" view, the
 * same split Phase 7 established for skills (see SkillsOverviewPage).
 *
 * Phase 47 adds the org-wide Risk register below the per-project one — a
 * read-only view of every Risk across every project in the active
 * organization at once (project/status/exposure filters, real server-side
 * pagination via GET /api/v1/risks), answering the question the
 * per-project register above cannot: "which projects across this whole
 * organization currently carry risk?" See
 * docs/adr/0047-org-wide-risk-register.md.
 */
export function RisksOverviewPage() {
  const { can } = useAuth()
  const canManageRisks = can('risk.write')
  const [searchParams, setSearchParams] = useSearchParams()
  const projectId = searchParams.get('project') ?? undefined

  const risksQuery = useRisks(projectId)
  const updateRisk = useUpdateRisk(projectId ?? '')
  const deleteRisk = useDeleteRisk(projectId ?? '')
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
        title="Risks"
        description="What could go wrong on a project, how exposed we are, and who owns following up."
      />

      <Card>
        <CardHeader
          title="Project risk register"
          description="Every recorded risk for the selected project."
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
              }}
            />
          </div>

          {!projectId ? (
            <EmptyState title="Select a project to view or record its risks." />
          ) : (
            <QueryBoundary query={risksQuery} loadingLabel="Loading risks…">
              {(risks) => (
                <div className="space-y-4">
                  <RisksTable
                    risks={risks}
                    personLabels={personLabels}
                    canManage={canManageRisks}
                    onStatusChange={(riskId, status: RiskStatus) =>
                      updateRisk.mutate({ riskId, data: { status } })
                    }
                    onRemove={(riskId) => deleteRisk.mutate(riskId)}
                    updatingId={
                      updateRisk.isPending
                        ? updateRisk.variables?.riskId
                        : undefined
                    }
                    removingId={
                      deleteRisk.isPending
                        ? (deleteRisk.variables as string | undefined)
                        : undefined
                    }
                  />
                  {canManageRisks ? (
                    <RiskForm projectId={projectId} />
                  ) : (
                    <ViewOnlyNotice message="Your role can view risks but not create or edit them." />
                  )}
                </div>
              )}
            </QueryBoundary>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Organization-wide risk register"
          description="Every risk recorded across every project in this organization — read-only. Filter by project, status, or exposure."
        />
        <CardBody className="space-y-4">
          <OrgRiskManager personLabels={personLabels} />
        </CardBody>
      </Card>
    </div>
  )
}

function OrgRiskManager({ personLabels }: { personLabels: Map<string, string> }) {
  const [projectFilter, setProjectFilter] = useState<string | undefined>(undefined)
  const [statusFilter, setStatusFilter] = useState<RiskStatus | ''>('')
  const [exposureFilter, setExposureFilter] = useState<RiskExposure | ''>('')
  const [offset, setOffset] = useState(0)

  const projectsLookup = useProjectsLookup()
  const projectLabels = useMemo(() => {
    const labels = new Map<string, string>()
    for (const [id, project] of projectsLookup) {
      labels.set(id, project.name)
    }
    return labels
  }, [projectsLookup])

  const filters = {
    project_id: projectFilter,
    status: statusFilter || undefined,
    exposure: exposureFilter || undefined,
    offset,
  }
  const risksQuery = useOrgRisks(filters)

  function resetToFirstPage() {
    setOffset(0)
  }

  const isFiltered = Boolean(projectFilter || statusFilter || exposureFilter)
  const total = risksQuery.data?.total ?? 0
  const hasPrevious = offset > 0
  const hasNext = offset + RISK_REGISTER_PAGE_SIZE < total

  return (
    <div className="space-y-4">
      <OrgRiskFilterBar
        projectId={projectFilter}
        onProjectChange={(value) => {
          setProjectFilter(value)
          resetToFirstPage()
        }}
        statusValue={statusFilter}
        onStatusChange={(value) => {
          setStatusFilter(value)
          resetToFirstPage()
        }}
        exposureValue={exposureFilter}
        onExposureChange={(value) => {
          setExposureFilter(value)
          resetToFirstPage()
        }}
      />

      <QueryBoundary query={risksQuery} loadingLabel="Loading the organization's risks…">
        {(page) => (
          <div className="space-y-3">
            <OrgRiskRegisterTable
              risks={page.items}
              projectLabels={projectLabels}
              personLabels={personLabels}
              isFiltered={isFiltered}
            />
            {page.total > 0 ? (
              <div className="flex items-center justify-between gap-4 text-xs text-slate-400">
                <span>
                  Showing {offset + 1}–{Math.min(offset + RISK_REGISTER_PAGE_SIZE, page.total)}{' '}
                  of {page.total} risk{page.total === 1 ? '' : 's'}
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    onClick={() =>
                      setOffset((prev) => Math.max(prev - RISK_REGISTER_PAGE_SIZE, 0))
                    }
                    disabled={!hasPrevious}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => setOffset((prev) => prev + RISK_REGISTER_PAGE_SIZE)}
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

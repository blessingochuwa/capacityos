import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { ProjectFilterPicker } from '@/features/insights/components/ProjectFilterPicker'
import { usePeopleLookup } from '@/hooks/usePeople'
import { RiskForm } from '../components/RiskForm'
import { RisksTable } from '../components/RisksTable'
import { useDeleteRisk, useUpdateRisk } from '../hooks/useRiskMutations'
import { useRisks } from '../hooks/useRisks'
import type { RiskStatus } from '../types/risks'

/**
 * "What could go wrong on this project, and who owns following up?"
 * (CLAUDE.md §17/§38) — a project's risk register: description, cause,
 * potential effect, probability/impact (exposure derived server-side, never
 * recomputed here — CLAUDE.md §4), response, owner, status, and review
 * date. High-exposure and overdue-review risks also surface as signals on
 * the existing Insights page (features/insights/) — this page is the "what
 * do we have" register; Insights is the "where should I look" view, the
 * same split Phase 7 established for skills (see SkillsOverviewPage).
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
    </div>
  )
}

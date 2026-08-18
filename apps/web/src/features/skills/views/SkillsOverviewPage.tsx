import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { DateRangeControl } from '@/features/capacity/components/DateRangeControl'
import { ProjectFilterPicker } from '@/features/insights/components/ProjectFilterPicker'
import { TeamPicker } from '@/features/capacity/components/TeamPicker'
import { thisWeek } from '@/features/capacity/utils/dateRange'
import { CreateSkillForm } from '../components/CreateSkillForm'
import { PersonPicker } from '../components/PersonPicker'
import { PersonSkillsPanel } from '../components/PersonSkillsPanel'
import { ProjectSkillCoverageTable } from '../components/ProjectSkillCoverageTable'
import { ProjectSkillRequirementForm } from '../components/ProjectSkillRequirementForm'
import { SkillsTable } from '../components/SkillsTable'
import { TeamSkillCapacityTable } from '../components/TeamSkillCapacityTable'
import { useDeactivateSkill } from '../hooks/useSkillMutations'
import { useSkills } from '../hooks/useSkills'
import { useProjectSkillCoverage } from '../hooks/useProjectSkillCoverage'
import { useRemoveProjectSkillRequirement } from '../hooks/useProjectSkillRequirements'
import { useTeamSkillCapacity } from '../hooks/useTeamSkillCapacity'
import { useState } from 'react'

const DEFAULT_RANGE = thisWeek()

/**
 * "Do we have the skills to execute the planned work?" (CLAUDE.md §38/Phase
 * 7) — skill inventory, per-project coverage, and per-team qualified
 * capacity. Bottleneck SIGNALS (skill_gap, single_skill_holder,
 * skill_concentration) are not shown here — they already surface through
 * the existing Insights page (features/insights/), which folds them into
 * the same signal list as every other Phase 5 signal. This page is the
 * "what do we have" inventory view; Insights is the "where should I look"
 * decision-support view. See docs/adr/0007-phase-7-skills-bottleneck-analysis.md.
 */
export function SkillsOverviewPage() {
  const { can } = useAuth()
  const canManageSkills = can('skill.write')
  const [searchParams, setSearchParams] = useSearchParams()
  const teamId = searchParams.get('team') ?? undefined
  const projectId = searchParams.get('project') ?? undefined
  const start = searchParams.get('start') ?? DEFAULT_RANGE.start
  const end = searchParams.get('end') ?? DEFAULT_RANGE.end
  const [personId, setPersonId] = useState<string | undefined>(undefined)

  function updateParam(key: string, value: string | undefined) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearchParams(next, { replace: true })
  }

  const range = { start_date: start, end_date: end }
  const skillsQuery = useSkills()
  const deactivateSkill = useDeactivateSkill()
  const coverageQuery = useProjectSkillCoverage(projectId, range)
  const teamCapacityQuery = useTeamSkillCapacity(teamId, range)
  const removeRequirement = useRemoveProjectSkillRequirement(projectId ?? '')

  return (
    <div className="space-y-6">
      <PageHeader
        title="Skills"
        description="What capabilities do we have, where are they concentrated, and do projects have the qualified capacity they need?"
      />

      <Card>
        <CardHeader
          title="Skill inventory"
          description="Every skill people can hold and projects can require."
        />
        <CardBody className="space-y-4">
          {canManageSkills ? (
            <CreateSkillForm />
          ) : (
            <ViewOnlyNotice message="Your role can view skills but not create or edit them." />
          )}
          <QueryBoundary query={skillsQuery} loadingLabel="Loading skills…">
            {(data) => (
              <SkillsTable
                skills={data.items}
                onDeactivate={(skillId) => deactivateSkill.mutate(skillId)}
                deactivatingId={
                  deactivateSkill.isPending
                    ? (deactivateSkill.variables as string | undefined)
                    : undefined
                }
                canManage={canManageSkills}
              />
            )}
          </QueryBoundary>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Person skills"
          description="Record an explicit proficiency for a person — never inferred from job title or allocation history."
        />
        <CardBody className="space-y-4">
          <div className="w-64">
            <PersonPicker value={personId} onChange={setPersonId} />
          </div>
          {personId ? (
            <PersonSkillsPanel personId={personId} />
          ) : (
            <EmptyState title="Select a person to view or edit their skills." />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Project skill coverage"
          description="Required capacity vs qualified available capacity, per skill."
        />
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-64">
              <ProjectFilterPicker
                value={projectId}
                onChange={(value) => updateParam('project', value)}
              />
            </div>
            <DateRangeControl
              range={{ start, end }}
              onChange={(range) =>
                setSearchParams(
                  (prev) => {
                    const next = new URLSearchParams(prev)
                    next.set('start', range.start)
                    next.set('end', range.end)
                    return next
                  },
                  { replace: true },
                )
              }
            />
          </div>
          {!projectId ? (
            <EmptyState title="Select a project to view its skill coverage." />
          ) : (
            <QueryBoundary query={coverageQuery} loadingLabel="Loading coverage…">
              {(coverage) => (
                <div className="space-y-4">
                  <ProjectSkillCoverageTable
                    requirements={coverage.requirements}
                    onRemove={(requirementId) => removeRequirement.mutate(requirementId)}
                    removingId={
                      removeRequirement.isPending
                        ? (removeRequirement.variables as string | undefined)
                        : undefined
                    }
                  />
                  <ProjectSkillRequirementForm
                    projectId={projectId}
                    excludeSkillIds={coverage.requirements.map((r) => r.skill_id)}
                  />
                </div>
              )}
            </QueryBoundary>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Team skill capacity"
          description="Qualified available capacity by skill across a team's members."
        />
        <CardBody className="space-y-4">
          <div className="w-64">
            <TeamPicker value={teamId} onChange={(value) => updateParam('team', value)} />
          </div>
          {!teamId ? (
            <EmptyState title="Select a team to view its skill capacity." />
          ) : (
            <QueryBoundary query={teamCapacityQuery} loadingLabel="Loading team capacity…">
              {(capacity) => <TeamSkillCapacityTable skills={capacity.skills} />}
            </QueryBoundary>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

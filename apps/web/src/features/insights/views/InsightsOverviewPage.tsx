import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useTeams } from '@/hooks/useTeams'
import { TeamPicker } from '@/features/capacity/components/TeamPicker'
import { DateRangeControl } from '@/features/capacity/components/DateRangeControl'
import { thisWeek } from '@/features/capacity/utils/dateRange'
import { SummarizeButton } from '@/features/ai/components/SummarizeButton'
import { ConcentrationAreasList } from '../components/ConcentrationAreasList'
import { PlanningHealthSummary } from '../components/PlanningHealthSummary'
import { ProjectFilterPicker } from '../components/ProjectFilterPicker'
import { ProjectsUnderPressureList } from '../components/ProjectsUnderPressureList'
import { ScenarioFilterPicker } from '../components/ScenarioFilterPicker'
import { SignalDetailPanel } from '../components/SignalDetailPanel'
import { SignalList } from '../components/SignalList'
import { UtilizationDistributionList } from '../components/UtilizationDistributionList'
import { useProjectSignals } from '../hooks/useProjectSignals'
import { useScenarioSignals } from '../hooks/useScenarioSignals'
import { useTeamSignals } from '../hooks/useTeamSignals'
import { useTeamSummary } from '../hooks/useTeamSummary'
import { signalKey, sortSignals } from '../utils/presentation'
import type { Signal } from '../types/insights'

const DEFAULT_RANGE = thisWeek()

/**
 * "Where should I look?" (CLAUDE.md §20/§38) — a prioritized, explainable
 * view on top of the existing capacity and scenario engines. Team, date
 * range, and optional project/scenario filters all live in the URL so the
 * current view is always shareable and survives a refresh, same convention
 * as features/capacity/views/CapacityOverviewPage.tsx.
 */
export function InsightsOverviewPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const teamsQuery = useTeams()

  const teamId = searchParams.get('team') ?? undefined
  const projectId = searchParams.get('project') ?? undefined
  const scenarioId = searchParams.get('scenario') ?? undefined
  const start = searchParams.get('start') ?? DEFAULT_RANGE.start
  const end = searchParams.get('end') ?? DEFAULT_RANGE.end
  const selectedSignal = searchParams.get('signal') ?? undefined

  // If exactly one team exists and none is selected yet, default to it
  // rather than making the user pick from a list of one.
  useEffect(() => {
    if (!teamId && teamsQuery.data?.items.length === 1) {
      const next = new URLSearchParams(searchParams)
      next.set('team', teamsQuery.data.items[0].id)
      setSearchParams(next, { replace: true })
    }
  }, [teamId, teamsQuery.data, searchParams, setSearchParams])

  function updateParam(key: string, value: string | undefined) {
    const next = new URLSearchParams(searchParams)
    if (value) {
      next.set(key, value)
    } else {
      next.delete(key)
    }
    // Any filter change invalidates whichever signal row was expanded.
    next.delete('signal')
    setSearchParams(next, { replace: true })
  }

  function handleSelectSignal(key: string) {
    const next = new URLSearchParams(searchParams)
    if (searchParams.get('signal') === key) {
      next.delete('signal')
    } else {
      next.set('signal', key)
    }
    setSearchParams(next, { replace: true })
  }

  const range = { start_date: start, end_date: end }
  const summaryQuery = useTeamSummary(teamId, range, { projectId, scenarioId })
  const teamSignalsQuery = useTeamSignals(teamId, range)
  const projectSignalsQuery = useProjectSignals(projectId, range)
  const scenarioSignalsQuery = useScenarioSignals(
    scenarioId,
    scenarioId !== undefined,
  )

  return (
    <div>
      <PageHeader
        title="Operational Insights"
        description="Where should you look? Prioritized capacity signals across people, teams, and projects."
      />

      <Card className="mb-6">
        <CardBody className="flex flex-wrap items-end gap-4">
          <div className="w-56">
            <TeamPicker
              value={teamId}
              onChange={(value) => updateParam('team', value)}
            />
          </div>
          <div className="w-56">
            <ProjectFilterPicker
              value={projectId}
              onChange={(value) => updateParam('project', value)}
            />
          </div>
          <div className="w-56">
            <ScenarioFilterPicker
              value={scenarioId}
              onChange={(value) => updateParam('scenario', value)}
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
                  next.delete('signal')
                  return next
                },
                { replace: true },
              )
            }
          />
        </CardBody>
      </Card>

      {!teamId ? (
        <Card>
          <CardBody>
            <EmptyState
              title="Select a team to view operational insights."
              description="Choose a team above to see prioritized capacity signals for the selected period."
            />
          </CardBody>
        </Card>
      ) : (
        <QueryBoundary query={summaryQuery} loadingLabel="Loading insights…">
          {(summary) => {
            const signals: Signal[] = sortSignals([
              ...(teamSignalsQuery.data?.items ?? []),
              ...(projectId ? (projectSignalsQuery.data?.items ?? []) : []),
              ...(scenarioId ? (scenarioSignalsQuery.data?.items ?? []) : []),
            ])
            const selected = signals.find(
              (signal) => signalKey(signal) === selectedSignal,
            )

            return (
              <div className="space-y-6">
                <Card>
                  <CardHeader title="Planning health" />
                  <CardBody>
                    <PlanningHealthSummary summary={summary} />
                  </CardBody>
                </Card>

                <SummarizeButton
                  entityType="team"
                  entityId={teamId}
                  startDate={start}
                  endDate={end}
                />

                <Card>
                  <CardHeader
                    title="Attention required"
                    description="Critical first, then new scenario risk, then warnings and informational signals."
                  />
                  <CardBody>
                    <QueryBoundary
                      query={teamSignalsQuery}
                      loadingLabel="Loading signals…"
                    >
                      {() => (
                        <SignalList
                          signals={signals}
                          selectedKey={selectedSignal}
                          onSelect={handleSelectSignal}
                        />
                      )}
                    </QueryBoundary>
                  </CardBody>
                </Card>

                {selected ? <SignalDetailPanel signal={selected} /> : null}

                <div className="grid gap-6 lg:grid-cols-2">
                  <Card>
                    <CardHeader
                      title="Concentration risk"
                      description="Projects whose hours are concentrated in a small number of people."
                    />
                    <CardBody>
                      <ConcentrationAreasList
                        areas={summary.concentration_areas}
                      />
                    </CardBody>
                  </Card>
                  <Card>
                    <CardHeader
                      title="Projects under pressure"
                      description="Assigned people's capacity vs this project's demand."
                    />
                    <CardBody>
                      <ProjectsUnderPressureList
                        projects={summary.projects_under_pressure}
                      />
                    </CardBody>
                  </Card>
                </div>

                <Card>
                  <CardHeader
                    title="Utilization distribution"
                    description="Who has the least — and the most — room in this period."
                  />
                  <CardBody>
                    <UtilizationDistributionList
                      points={summary.utilization_distribution}
                    />
                  </CardBody>
                </Card>
              </div>
            )
          }}
        </QueryBoundary>
      )}
    </div>
  )
}

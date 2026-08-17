import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { MetricTile } from '@/components/ui/MetricTile'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useTeams } from '@/hooks/useTeams'
import { usePeopleLookup } from '@/hooks/usePeople'
import { toNumber } from '@/lib/decimal'
import { SummarizeButton } from '@/features/ai/components/SummarizeButton'
import { CapacitySummary } from '../components/CapacitySummary'
import { TeamCapacityTable } from '../components/TeamCapacityTable'
import { OverAllocationPanel } from '../components/OverAllocationPanel'
import { AvailableCapacityPanel } from '../components/AvailableCapacityPanel'
import { TeamPicker } from '../components/TeamPicker'
import { DateRangeControl } from '../components/DateRangeControl'
import { useTeamCapacity } from '../hooks/useTeamCapacity'
import { thisWeek } from '../utils/dateRange'

const DEFAULT_RANGE = thisWeek()

/**
 * "Where is capacity at risk?" (CLAUDE.md §38). Team + date range live in
 * the URL (?team=&start=&end=) so the current view is always shareable and
 * survives a refresh (spec §16).
 */
export function CapacityOverviewPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const teamsQuery = useTeams()
  const peopleLookup = usePeopleLookup()

  const teamId = searchParams.get('team') ?? undefined
  const start = searchParams.get('start') ?? DEFAULT_RANGE.start
  const end = searchParams.get('end') ?? DEFAULT_RANGE.end

  // If exactly one team exists and none is selected yet, default to it
  // rather than making the user pick from a list of one.
  useEffect(() => {
    if (!teamId && teamsQuery.data?.items.length === 1) {
      const next = new URLSearchParams(searchParams)
      next.set('team', teamsQuery.data.items[0].id)
      setSearchParams(next, { replace: true })
    }
  }, [teamId, teamsQuery.data, searchParams, setSearchParams])

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams)
    next.set(key, value)
    setSearchParams(next, { replace: true })
  }

  function handleReset() {
    setSearchParams(
      { start: DEFAULT_RANGE.start, end: DEFAULT_RANGE.end },
      { replace: true },
    )
  }

  const teamCapacityQuery = useTeamCapacity(teamId, {
    start_date: start,
    end_date: end,
  })

  return (
    <div>
      <PageHeader
        title="Capacity Overview"
        description="Where is capacity at risk, and who or what is affected?"
      />

      <Card className="mb-6">
        <CardBody className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-56">
              <TeamPicker
                value={teamId}
                onChange={(value) => updateParam('team', value)}
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
          <Button variant="ghost" onClick={handleReset}>
            Reset filters
          </Button>
        </CardBody>
      </Card>

      {!teamId ? (
        <Card>
          <CardBody>
            <EmptyState
              title="Select a team to view capacity."
              description="Choose a team above to see who has room, who's overloaded, and where the constraint is."
            />
          </CardBody>
        </Card>
      ) : (
        <QueryBoundary
          query={teamCapacityQuery}
          loadingLabel="Loading team capacity…"
        >
          {(team) => {
            const overCount = team.members.filter(
              (member) => toNumber(member.over_allocation) > 0,
            ).length
            const availableCount = team.members.filter(
              (member) => toNumber(member.remaining_capacity) > 0,
            ).length

            return (
              <div className="space-y-6">
                <Card>
                  <CardBody className="space-y-6">
                    <CapacitySummary totals={team} />
                    <div className="grid grid-cols-2 gap-4 border-t border-slate-800 pt-4 sm:w-1/2">
                      <MetricTile
                        label="People over capacity"
                        value={overCount}
                        tone={overCount > 0 ? 'danger' : 'default'}
                      />
                      <MetricTile
                        label="People with available capacity"
                        value={availableCount}
                        tone={availableCount > 0 ? 'success' : 'default'}
                      />
                    </div>
                  </CardBody>
                </Card>

                <SummarizeButton
                  entityType="team"
                  entityId={teamId}
                  startDate={start}
                  endDate={end}
                />

                <div className="grid gap-6 lg:grid-cols-2">
                  <Card>
                    <CardHeader
                      title="Needs attention"
                      description="Over-allocated people in this period."
                    />
                    <CardBody>
                      <OverAllocationPanel
                        members={team.members}
                        peopleLookup={peopleLookup}
                      />
                    </CardBody>
                  </Card>
                  <Card>
                    <CardHeader
                      title="Available capacity"
                      description="People with meaningful remaining capacity."
                    />
                    <CardBody>
                      <AvailableCapacityPanel
                        members={team.members}
                        peopleLookup={peopleLookup}
                      />
                    </CardBody>
                  </Card>
                </div>

                <Card>
                  <CardHeader
                    title="Team roster"
                    description="Every person's capacity for this period."
                  />
                  <CardBody>
                    <TeamCapacityTable
                      members={team.members}
                      peopleLookup={peopleLookup}
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

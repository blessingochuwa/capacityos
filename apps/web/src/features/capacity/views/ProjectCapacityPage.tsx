import { Link, useParams, useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { MetricTile } from '@/components/ui/MetricTile'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { usePeopleLookup } from '@/hooks/usePeople'
import { useProjectsLookup } from '@/hooks/useProjects'
import { ProjectDemandTimeline } from '../components/ProjectDemandTimeline'
import { ProjectPersonBreakdown } from '../components/ProjectPersonBreakdown'
import { DateRangeControl } from '../components/DateRangeControl'
import { useProjectDemand } from '../hooks/useProjectDemand'
import { formatHours } from '../utils/presentation'
import { thisWeek } from '../utils/dateRange'

const DEFAULT_RANGE = thisWeek()

/** "Do we have enough capacity to deliver this?" (CLAUDE.md §38) — demand
 * only, no forecasting: a project has no working schedule of its own to
 * compare allocated hours against (spec §12/§19). */
export function ProjectCapacityPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const peopleLookup = usePeopleLookup()
  const projectsLookup = useProjectsLookup()

  const start = searchParams.get('start') ?? DEFAULT_RANGE.start
  const end = searchParams.get('end') ?? DEFAULT_RANGE.end

  const demandQuery = useProjectDemand(projectId, {
    start_date: start,
    end_date: end,
  })
  const project = projectId ? projectsLookup.get(projectId) : undefined

  return (
    <div>
      <p className="mb-2 text-sm">
        <Link to="/capacity" className="text-slate-400 hover:text-slate-200">
          ← Back to Capacity Overview
        </Link>
      </p>
      <PageHeader
        title={project?.name ?? 'Project capacity'}
        description={
          project?.description ??
          'What demand has this project placed on the team?'
        }
      />

      <Card className="mb-6">
        <CardBody>
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
        </CardBody>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardBody>
            <QueryBoundary
              query={demandQuery}
              loadingLabel="Loading project demand…"
            >
              {(demand) => (
                <div className="grid grid-cols-2 gap-4 sm:w-1/2">
                  <MetricTile
                    label="Allocated capacity"
                    value={formatHours(demand.allocated_hours)}
                  />
                  <MetricTile
                    label="People allocated"
                    value={demand.allocated_people}
                  />
                </div>
              )}
            </QueryBoundary>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Daily demand"
            description="When is this project drawing the most capacity?"
          />
          <CardBody>
            <QueryBoundary
              query={demandQuery}
              loadingLabel="Loading daily demand…"
            >
              {(demand) => (
                <ProjectDemandTimeline daily={demand.daily_breakdown} />
              )}
            </QueryBoundary>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="By person"
            description="Who this project's demand is allocated to."
          />
          <CardBody>
            <QueryBoundary
              query={demandQuery}
              loadingLabel="Loading breakdown…"
            >
              {(demand) => (
                <ProjectPersonBreakdown
                  byPerson={demand.by_person}
                  peopleLookup={peopleLookup}
                />
              )}
            </QueryBoundary>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

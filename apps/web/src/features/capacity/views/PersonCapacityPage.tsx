import { useSearchParams, useParams, Link } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { usePeopleLookup } from '@/hooks/usePeople'
import { useProjectsLookup } from '@/hooks/useProjects'
import { SummarizeButton } from '@/features/ai/components/SummarizeButton'
import { CapacitySummary } from '../components/CapacitySummary'
import { DailyCapacityTimeline } from '../components/DailyCapacityTimeline'
import { AllocationsList } from '../components/AllocationsList'
import { AvailabilityExceptionsList } from '../components/AvailabilityExceptionsList'
import { DateRangeControl } from '../components/DateRangeControl'
import { usePersonCapacity } from '../hooks/usePersonCapacity'
import {
  usePersonAllocations,
  usePersonAvailabilityExceptions,
} from '../hooks/usePersonAllocations'
import { thisWeek } from '../utils/dateRange'

const DEFAULT_RANGE = thisWeek()

/** Overlaps [start,end] — a plain date-range membership check, not a
 * capacity calculation, so allocations/exceptions shown here are scoped to
 * the period actually being viewed even though the underlying list
 * endpoints return everything for the person. */
function overlapsRange(
  itemStart: string,
  itemEnd: string,
  start: string,
  end: string,
): boolean {
  return itemStart <= end && itemEnd >= start
}

export function PersonCapacityPage() {
  const { personId } = useParams<{ personId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const peopleLookup = usePeopleLookup()
  const projectsLookup = useProjectsLookup()

  const start = searchParams.get('start') ?? DEFAULT_RANGE.start
  const end = searchParams.get('end') ?? DEFAULT_RANGE.end

  const capacityQuery = usePersonCapacity(personId, {
    start_date: start,
    end_date: end,
  })
  const allocationsQuery = usePersonAllocations(personId)
  const exceptionsQuery = usePersonAvailabilityExceptions(personId)

  const person = personId ? peopleLookup.get(personId) : undefined

  return (
    <div>
      <p className="mb-2 text-sm">
        <Link to="/capacity" className="text-slate-400 hover:text-slate-200">
          ← Back to Capacity Overview
        </Link>
      </p>
      <PageHeader
        title={person?.display_name ?? 'Person capacity'}
        description={person?.job_title ?? 'Can I give this person more work?'}
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
              query={capacityQuery}
              loadingLabel="Loading capacity…"
            >
              {(capacity) => <CapacitySummary totals={capacity} />}
            </QueryBoundary>
          </CardBody>
        </Card>

        {personId ? (
          <SummarizeButton
            entityType="person"
            entityId={personId}
            startDate={start}
            endDate={end}
          />
        ) : null}

        <Card>
          <CardHeader
            title="Daily capacity"
            description="When is this person constrained in this period?"
          />
          <CardBody>
            <QueryBoundary
              query={capacityQuery}
              loadingLabel="Loading daily capacity…"
            >
              {(capacity) => (
                <DailyCapacityTimeline daily={capacity.daily_breakdown} />
              )}
            </QueryBoundary>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Allocations"
            description="What work is driving this person's allocated capacity."
          />
          <CardBody>
            <QueryBoundary
              query={allocationsQuery}
              loadingLabel="Loading allocations…"
            >
              {(page) => (
                <AllocationsList
                  allocations={page.items.filter((allocation) =>
                    overlapsRange(
                      allocation.start_date,
                      allocation.end_date,
                      start,
                      end,
                    ),
                  )}
                  projectsLookup={projectsLookup}
                />
              )}
            </QueryBoundary>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Availability exceptions"
            description="Leave, holidays, and other deviations from the normal schedule."
          />
          <CardBody>
            <QueryBoundary
              query={exceptionsQuery}
              loadingLabel="Loading availability exceptions…"
            >
              {(page) => (
                <AvailabilityExceptionsList
                  exceptions={page.items.filter((exception) =>
                    overlapsRange(
                      exception.start_date,
                      exception.end_date,
                      start,
                      end,
                    ),
                  )}
                />
              )}
            </QueryBoundary>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}

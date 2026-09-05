import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import type { Project } from '@/types/entities'
import type { DependencyGraph } from '../types/prioritization'
import {
  buildDependencyTimeline,
  type ScheduledProjectRow,
  type UnscheduledReason,
} from '../utils/dependencyTimeline'

const BAR_COLOR = '#818cf8'
const DAY_MS = 86_400_000

const UNSCHEDULED_REASON_LABEL: Record<UnscheduledReason, string> = {
  no_dates: 'No start or end date',
  no_start_date: 'No start date',
  no_end_date: 'No end date',
}

function parseDay(iso: string): number {
  return Date.parse(`${iso}T00:00:00Z`)
}

function formatShortDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

interface ChartRow {
  project_name: string
  /** [startOffsetDays, endOffsetDays] from the timeline's range start;
   * end is +1 day so a same-day project still has a visible width. */
  span: [number, number]
  start_date: string
  end_date: string
}

function toChartRow(row: ScheduledProjectRow, rangeStart: string): ChartRow {
  const startOffset = Math.round((parseDay(row.start_date) - parseDay(rangeStart)) / DAY_MS)
  const endOffset = Math.round((parseDay(row.end_date) - parseDay(rangeStart)) / DAY_MS)
  return {
    project_name: row.project_name,
    span: [startOffset, endOffset + 1],
    start_date: row.start_date,
    end_date: row.end_date,
  }
}

interface BarTooltipPayloadEntry {
  payload: ChartRow
}

function BarTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: BarTooltipPayloadEntry[]
}) {
  if (!active || !payload || payload.length === 0) return null
  const row = payload[0].payload
  return (
    <div className="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 shadow-lg">
      <p className="mb-1 font-medium text-slate-100">{row.project_name}</p>
      <p>
        {formatShortDate(row.start_date)} → {formatShortDate(row.end_date)}
      </p>
    </div>
  )
}

/**
 * Phase 40 — the PRD's §15 "Dependency timeline". Answers "how are our
 * projects scheduled relative to the dependencies between them?" by
 * placing every fully-dated project on a shared date axis (`start_date` →
 * `end_date`, verbatim) and listing the `blocks` relationships between
 * them. Built entirely from GET /api/v1/projects + GET
 * /api/v1/prioritization/dependency-graph — both already authorized and
 * organization-scoped — with no new backend endpoint (mirrors Phase
 * 24/25/27's frontend-only precedent).
 *
 * Deliberately excluded (Phase 39 decisions, see docs/adr/0040):
 * projects without both dates are shown in a separate "Unscheduled"
 * section, never fabricated onto the axis; `related`/`enables` edges are
 * not drawn; no schedule-consistency warning is computed; the view is
 * read-only (no editing/drag/create/delete).
 *
 * Chart (aria-hidden) + accessible table pairing matches
 * ProjectDemandTimeline / PriorityEffortScatterChart exactly — no
 * information is conveyed by colour or position alone.
 */
export function DependencyTimeline({
  projects,
  graph,
}: {
  projects: Project[]
  graph: DependencyGraph
}) {
  const model = buildDependencyTimeline(projects, graph)

  if (projects.length === 0) {
    return (
      <EmptyState
        title="No projects yet."
        description="Add projects with start and end dates to see them on the dependency timeline."
      />
    )
  }

  const { scheduled, unscheduled, blocksEdges, rangeStart } = model
  const chartRows = rangeStart ? scheduled.map((row) => toChartRow(row, rangeStart)) : []
  const chartHeight = Math.min(480, Math.max(140, chartRows.length * 40 + 48))

  return (
    <div className="space-y-8">
      <section className="space-y-4" aria-labelledby="dependency-timeline-scheduled">
        <h3
          id="dependency-timeline-scheduled"
          className="text-sm font-medium text-slate-200"
        >
          Scheduled projects
        </h3>

        {scheduled.length === 0 ? (
          <p className="text-sm text-slate-400">
            No scheduled projects yet. Every project below is missing a start or end
            date.
          </p>
        ) : (
          <>
            <div
              className="w-full overflow-x-auto"
              style={{ height: chartHeight }}
              aria-hidden="true"
            >
              <ResponsiveContainer width="100%" height="100%" minWidth={480}>
                <BarChart
                  layout="vertical"
                  data={chartRows}
                  margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                  <XAxis
                    type="number"
                    dataKey="span"
                    stroke="#64748b"
                    fontSize={12}
                    tickLine={false}
                    tickFormatter={(offset: number) =>
                      rangeStart
                        ? formatShortDate(
                            new Date(parseDay(rangeStart) + offset * DAY_MS)
                              .toISOString()
                              .slice(0, 10),
                          )
                        : String(offset)
                    }
                  />
                  <YAxis
                    type="category"
                    dataKey="project_name"
                    stroke="#64748b"
                    fontSize={12}
                    tickLine={false}
                    width={140}
                  />
                  <Tooltip content={<BarTooltip />} cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }} />
                  <Bar dataKey="span" fill={BAR_COLOR} radius={[3, 3, 3, 3]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="max-h-96 overflow-y-auto">
              <Table caption="Scheduled projects on the dependency timeline">
                <thead className="sticky top-0 bg-slate-900">
                  <tr>
                    <Th scope="col">Project</Th>
                    <Th scope="col">Start</Th>
                    <Th scope="col">End</Th>
                  </tr>
                </thead>
                <tbody>
                  {scheduled.map((row) => (
                    <tr key={row.project_id}>
                      <Td className="font-medium text-slate-100">{row.project_name}</Td>
                      <Td className="tabular-nums">{formatShortDate(row.start_date)}</Td>
                      <Td className="tabular-nums">{formatShortDate(row.end_date)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </>
        )}
      </section>

      <section className="space-y-4" aria-labelledby="dependency-timeline-blocks">
        <h3 id="dependency-timeline-blocks" className="text-sm font-medium text-slate-200">
          Blocking relationships
        </h3>
        {blocksEdges.length === 0 ? (
          <p className="text-sm text-slate-400">No blocking relationships recorded.</p>
        ) : (
          <Table caption="Blocking relationships between projects">
            <thead>
              <tr>
                <Th scope="col">Blocking project</Th>
                <Th scope="col">Relationship</Th>
                <Th scope="col">Blocked project</Th>
                <Th scope="col">On timeline</Th>
              </tr>
            </thead>
            <tbody>
              {blocksEdges.map((edge) => (
                <tr key={edge.id}>
                  <Td className="font-medium text-slate-200">{edge.from_project_name}</Td>
                  <Td>
                    <Badge variant="neutral">blocks</Badge>
                  </Td>
                  <Td className="font-medium text-slate-200">{edge.to_project_name}</Td>
                  <Td>
                    {edge.both_scheduled ? (
                      <span className="text-slate-400">Both scheduled</span>
                    ) : (
                      <Badge variant="warning">Involves an unscheduled project</Badge>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </section>

      {unscheduled.length > 0 ? (
        <section className="space-y-4" aria-labelledby="dependency-timeline-unscheduled">
          <h3
            id="dependency-timeline-unscheduled"
            className="text-sm font-medium text-slate-200"
          >
            Unscheduled projects
          </h3>
          <p className="text-sm text-slate-400">
            These projects have no fixed span on the timeline because a start or end
            date is missing. No dates are inferred for them.
          </p>
          <Table caption="Projects with no scheduled span">
            <thead>
              <tr>
                <Th scope="col">Project</Th>
                <Th scope="col">Status</Th>
                <Th scope="col">Missing</Th>
              </tr>
            </thead>
            <tbody>
              {unscheduled.map((row) => (
                <tr key={row.project_id}>
                  <Td className="font-medium text-slate-100">{row.project_name}</Td>
                  <Td className="capitalize text-slate-300">{row.status}</Td>
                  <Td className="text-slate-300">{UNSCHEDULED_REASON_LABEL[row.reason]}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </section>
      ) : null}
    </div>
  )
}

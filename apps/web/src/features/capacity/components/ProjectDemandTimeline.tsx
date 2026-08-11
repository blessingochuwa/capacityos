import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Table, Td, Th } from '@/components/ui/Table'
import { EmptyState } from '@/components/ui/EmptyState'
import type { ProjectDailyDemand } from '../types/capacity'
import { formatHours } from '../utils/presentation'

interface ProjectDemandTimelineProps {
  daily: ProjectDailyDemand[]
}

function formatShortDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

interface TooltipPayloadEntry {
  payload: ProjectDailyDemand
}

function DayTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: TooltipPayloadEntry[]
}) {
  if (!active || !payload || payload.length === 0) return null
  const day = payload[0].payload
  return (
    <div className="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 shadow-lg">
      <p className="mb-1 font-medium text-slate-100">
        {formatShortDate(day.date)}
      </p>
      <p>Allocated: {formatHours(day.allocated_hours)}</p>
    </div>
  )
}

/** Same pairing principle as DailyCapacityTimeline: chart + accessible table,
 * both driven by ProjectDemand.daily_breakdown exactly as returned by the API. */
export function ProjectDemandTimeline({ daily }: ProjectDemandTimelineProps) {
  if (daily.length === 0) {
    return <EmptyState title="No allocations found for this period." />
  }

  return (
    <div className="space-y-4">
      <div className="h-56 w-full" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={daily}
            margin={{ top: 8, right: 8, left: 0, bottom: 8 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e293b"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tickFormatter={formatShortDate}
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
            />
            <YAxis stroke="#64748b" fontSize={12} tickLine={false} width={32} />
            <Tooltip
              content={<DayTooltip />}
              cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }}
            />
            <Bar
              dataKey="allocated_hours"
              name="Allocated"
              fill="#818cf8"
              radius={[3, 3, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="max-h-80 overflow-y-auto">
        <Table caption="Daily project demand">
          <thead className="sticky top-0 bg-slate-900">
            <tr>
              <Th scope="col">Date</Th>
              <Th scope="col" className="text-right">
                Allocated
              </Th>
            </tr>
          </thead>
          <tbody>
            {daily.map((day) => (
              <tr key={day.date}>
                <Td>{formatShortDate(day.date)}</Td>
                <Td className="text-right tabular-nums">
                  {formatHours(day.allocated_hours)}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    </div>
  )
}

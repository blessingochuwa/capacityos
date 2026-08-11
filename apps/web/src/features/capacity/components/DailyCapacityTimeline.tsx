import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Table, Td, Th } from '@/components/ui/Table'
import { EmptyState } from '@/components/ui/EmptyState'
import { toNumber } from '@/lib/decimal'
import type { DailyCapacity } from '../types/capacity'
import { formatHours, formatUtilization } from '../utils/presentation'

interface DailyCapacityTimelineProps {
  daily: DailyCapacity[]
}

function formatShortDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

interface TooltipPayloadEntry {
  payload: DailyCapacity
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
      <p>Effective: {formatHours(day.effective_capacity)}</p>
      <p>Allocated: {formatHours(day.allocated_hours)}</p>
      <p>Remaining: {formatHours(day.remaining_capacity)}</p>
      <p>Utilization: {formatUtilization(day.utilization)}</p>
    </div>
  )
}

/**
 * "When are we actually constrained?" (spec §9). The chart is always paired
 * with the same data as a real <table> below it — the chart is supplementary,
 * never the only way to read the numbers (spec §9/§21). Every value plotted
 * comes directly from DailyCapacity as returned by the API; nothing here
 * recomputes effective/allocated/remaining/utilization.
 */
export function DailyCapacityTimeline({ daily }: DailyCapacityTimelineProps) {
  if (daily.length === 0) {
    return <EmptyState title="No daily capacity data for this period." />
  }

  return (
    <div className="space-y-4">
      <div className="h-64 w-full" aria-hidden="true">
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
              dataKey="effective_capacity"
              name="Effective"
              fill="#334155"
              radius={[3, 3, 0, 0]}
            />
            <Bar
              dataKey="allocated_hours"
              name="Allocated"
              radius={[3, 3, 0, 0]}
            >
              {daily.map((day) => (
                <Cell
                  key={day.date}
                  fill={
                    toNumber(day.over_allocation) > 0 ? '#f43f5e' : '#818cf8'
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="max-h-80 overflow-y-auto">
        <Table caption="Daily capacity breakdown">
          <thead className="sticky top-0 bg-slate-900">
            <tr>
              <Th scope="col">Date</Th>
              <Th scope="col" className="text-right">
                Scheduled
              </Th>
              <Th scope="col" className="text-right">
                Unavailable
              </Th>
              <Th scope="col" className="text-right">
                Effective
              </Th>
              <Th scope="col" className="text-right">
                Allocated
              </Th>
              <Th scope="col" className="text-right">
                Remaining
              </Th>
              <Th scope="col" className="text-right">
                Utilization
              </Th>
            </tr>
          </thead>
          <tbody>
            {daily.map((day) => (
              <tr key={day.date}>
                <Td>{formatShortDate(day.date)}</Td>
                <Td className="text-right tabular-nums">
                  {formatHours(day.scheduled_hours)}
                </Td>
                <Td className="text-right tabular-nums">
                  {formatHours(day.unavailable_hours)}
                </Td>
                <Td className="text-right tabular-nums">
                  {formatHours(day.effective_capacity)}
                </Td>
                <Td className="text-right tabular-nums">
                  {formatHours(day.allocated_hours)}
                </Td>
                <Td
                  className={`text-right tabular-nums ${toNumber(day.over_allocation) > 0 ? 'text-rose-300' : ''}`}
                >
                  {formatHours(day.remaining_capacity)}
                </Td>
                <Td className="text-right tabular-nums">
                  {formatUtilization(day.utilization)}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    </div>
  )
}

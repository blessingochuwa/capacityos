import { formatUtilization } from '@/features/capacity/utils/presentation'
import { bottomUtilization, topUtilization } from '../utils/presentation'
import type { UtilizationPoint } from '../types/insights'

const DISPLAY_COUNT = 3

export function UtilizationDistributionList({
  points,
}: {
  points: UtilizationPoint[]
}) {
  const highest = topUtilization(points, DISPLAY_COUNT)
  const lowest = bottomUtilization(points, DISPLAY_COUNT)

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Highest utilization
        </h3>
        <PointList points={highest} />
      </div>
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Lowest utilization
        </h3>
        <PointList points={lowest} />
      </div>
    </div>
  )
}

function PointList({ points }: { points: UtilizationPoint[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-slate-400">No team members in this period.</p>
  }
  return (
    <ul className="space-y-1 text-sm">
      {points.map((point) => (
        <li
          key={point.person_id}
          className="flex items-center justify-between text-slate-200"
        >
          <span>{point.label}</span>
          <span className="text-slate-400">
            {formatUtilization(point.utilization)}
          </span>
        </li>
      ))}
    </ul>
  )
}

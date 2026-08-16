import { EmptyState } from '@/components/ui/EmptyState'
import { formatUtilization } from '@/features/capacity/utils/presentation'
import type { ConcentrationArea } from '../types/insights'

export function ConcentrationAreasList({
  areas,
}: {
  areas: ConcentrationArea[]
}) {
  if (areas.length === 0) {
    return (
      <EmptyState
        title="No concentration risk detected."
        description="No project currently has its allocated hours concentrated in a small number of people."
      />
    )
  }

  return (
    <ul className="space-y-2 text-sm">
      {areas.map((area) => (
        <li
          key={area.project_id}
          className="flex flex-wrap items-center justify-between gap-2 text-slate-200"
        >
          <span>{area.project_label}</span>
          <span className="text-slate-400">
            {formatUtilization(area.ratio)} held by{' '}
            {area.top_contributor_labels.join(', ')}
          </span>
        </li>
      ))}
    </ul>
  )
}

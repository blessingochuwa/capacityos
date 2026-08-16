import { EmptyState } from '@/components/ui/EmptyState'
import { formatHours } from '@/features/capacity/utils/presentation'
import { SeverityBadge } from './SeverityBadge'
import type { ProjectPressure } from '../types/insights'

export function ProjectsUnderPressureList({
  projects,
}: {
  projects: ProjectPressure[]
}) {
  if (projects.length === 0) {
    return (
      <EmptyState
        title="No projects under capacity pressure."
        description="Every project's assigned people currently have enough capacity for the selected period."
      />
    )
  }

  return (
    <ul className="space-y-2 text-sm">
      {projects.map((project) => (
        <li
          key={project.project_id}
          className="flex flex-wrap items-center justify-between gap-2"
        >
          <div className="flex items-center gap-2">
            <SeverityBadge severity={project.severity} />
            <span className="text-slate-200">{project.project_label}</span>
          </div>
          <span className="text-slate-400">
            {formatHours(project.demand_hours)} demand ·{' '}
            {formatHours(project.remaining_capacity)} remaining
          </span>
        </li>
      ))}
    </ul>
  )
}

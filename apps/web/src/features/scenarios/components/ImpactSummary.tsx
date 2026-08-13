import { MetricTile } from '@/components/ui/MetricTile'
import { formatDateRange } from '@/features/capacity/utils/presentation'
import type { Impact } from '../types/scenario'

/** "Where did this scenario create change?" (prompt §8) — counts, not a
 * dump of every affected id; the People/Projects panels already list them. */
export function ImpactSummary({ impact }: { impact: Impact }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <MetricTile
        label="People affected"
        value={impact.affected_people.length}
      />
      <MetricTile
        label="Projects affected"
        value={impact.affected_projects.length}
      />
      <MetricTile label="Teams affected" value={impact.affected_teams.length} />
      <MetricTile
        label="Dates affected"
        value={
          impact.affected_start_date && impact.affected_end_date
            ? formatDateRange(
                impact.affected_start_date,
                impact.affected_end_date,
              )
            : '—'
        }
      />
    </div>
  )
}

import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { formatHours } from '@/features/capacity/utils/presentation'
import type { Risk } from '../types/scenario'

const RISK_SENTENCE: Record<Risk['type'], (risk: Risk) => string> = {
  over_allocation: (risk) =>
    `${risk.label} becomes over-allocated by ${formatHours(risk.scenario_value)}.`,
  zero_remaining_capacity: (risk) =>
    `${risk.label} would have no remaining capacity left.`,
}

/** New risks first (prompt §16: "prioritize new risks... avoid overwhelming
 * users with every unchanged metric") — the backend already sorts this way
 * (ScenarioCalculationService._risks), this just renders it. */
export function RiskList({ risks }: { risks: Risk[] }) {
  if (risks.length === 0) {
    return (
      <EmptyState
        title="No capacity risks in this scenario."
        description="Over-allocation and zero-remaining-capacity conflicts will appear here once you add changes and calculate."
      />
    )
  }

  return (
    <ul className="space-y-2">
      {risks.map((risk, index) => (
        <li
          key={`${risk.person_id}-${risk.type}-${index}`}
          className="flex items-start gap-2 text-sm text-slate-200"
        >
          {risk.is_new ? (
            <Badge variant="danger">New</Badge>
          ) : (
            <Badge variant="neutral">Ongoing</Badge>
          )}
          <span>{RISK_SENTENCE[risk.type](risk)}</span>
        </li>
      ))}
    </ul>
  )
}

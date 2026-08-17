import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { MetricTile } from '@/components/ui/MetricTile'
import {
  formatDateRange,
  formatHours,
  formatUtilization,
} from '@/features/capacity/utils/presentation'
import { SeverityBadge } from './SeverityBadge'
import { SIGNAL_TYPE_LABEL } from '../utils/presentation'
import type { Signal } from '../types/insights'

/** What/why/numbers/affected entities/baseline-vs-scenario for one selected
 * signal — every field rendered here is already on the Signal itself, so
 * selecting a row never triggers a second network request (signals are
 * computed, not stored, so there is nothing further to "load"). */
export function SignalDetailPanel({ signal }: { signal: Signal }) {
  return (
    <Card>
      <CardHeader
        title={SIGNAL_TYPE_LABEL[signal.type]}
        description={formatDateRange(signal.start_date, signal.end_date)}
        action={<SeverityBadge severity={signal.severity} />}
      />
      <CardBody className="space-y-4">
        <p className="text-sm text-slate-200">{signal.explanation}</p>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {signal.effective_capacity !== null ? (
            <MetricTile
              label="Effective capacity"
              value={formatHours(signal.effective_capacity)}
            />
          ) : null}
          {signal.allocated_hours !== null ? (
            <MetricTile
              label="Allocated"
              value={formatHours(signal.allocated_hours)}
            />
          ) : null}
          {signal.remaining_capacity !== null ? (
            <MetricTile
              label="Remaining"
              value={formatHours(signal.remaining_capacity)}
            />
          ) : null}
          {signal.utilization !== null ? (
            <MetricTile
              label="Utilization"
              value={formatUtilization(signal.utilization)}
            />
          ) : null}
          {signal.excess_hours !== null ? (
            <MetricTile
              label="Excess hours"
              value={formatHours(signal.excess_hours)}
              tone="danger"
            />
          ) : null}
          {signal.concentration_ratio !== null ? (
            <MetricTile
              label="Concentration"
              value={formatUtilization(signal.concentration_ratio)}
            />
          ) : null}
          {signal.skill_required_hours !== null ? (
            <MetricTile
              label="Required"
              value={formatHours(signal.skill_required_hours)}
            />
          ) : null}
          {signal.skill_qualified_available_hours !== null ? (
            <MetricTile
              label="Qualified available"
              value={formatHours(signal.skill_qualified_available_hours)}
            />
          ) : null}
          {signal.skill_gap_hours !== null ? (
            <MetricTile
              label="Gap"
              value={formatHours(signal.skill_gap_hours)}
              tone="danger"
            />
          ) : null}
          {signal.skill_holder_ratio !== null ? (
            <MetricTile
              label="Held by"
              value={formatUtilization(signal.skill_holder_ratio)}
            />
          ) : null}
        </div>
        {signal.skill_holder_labels !== null && signal.skill_holder_labels.length > 0 ? (
          <p className="text-xs text-slate-400">
            Holders: {signal.skill_holder_labels.join(', ')}
          </p>
        ) : null}
        {signal.affected_person_ids.length > 0 ? (
          <p className="text-xs text-slate-400">
            Affects {signal.affected_person_ids.length}{' '}
            {signal.affected_person_ids.length === 1 ? 'person' : 'people'}.
          </p>
        ) : null}
        {signal.scenario_id !== null ? (
          <p className="text-xs text-slate-400">
            {signal.is_new
              ? 'New in this scenario.'
              : `Existing risk — ${signal.trend ?? 'unchanged'} compared to baseline.`}
          </p>
        ) : null}
      </CardBody>
    </Card>
  )
}

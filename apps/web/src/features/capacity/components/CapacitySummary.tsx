import { MetricTile } from '@/components/ui/MetricTile'
import { InfoTooltip } from '@/components/ui/InfoTooltip'
import { StatusBadge } from './StatusBadge'
import { CapacityBar } from './CapacityBar'
import {
  formatHours,
  formatOverAllocation,
  formatUtilization,
  getCapacityStatus,
} from '../utils/presentation'

/** The fields shared by PersonCapacity and TeamCapacity — both satisfy this
 * structurally, so this component works for either without a cast. */
export interface CapacityTotals {
  effective_capacity: string
  allocated_hours: string
  remaining_capacity: string
  utilization: string | null
  over_allocation: string
}

export function CapacitySummary({ totals }: { totals: CapacityTotals }) {
  const status = getCapacityStatus(totals.utilization, totals.over_allocation)
  const overNote = formatOverAllocation(totals.over_allocation)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <StatusBadge status={status} />
      </div>
      <CapacityBar
        effectiveCapacity={totals.effective_capacity}
        allocatedCapacity={totals.allocated_hours}
        remainingCapacity={totals.remaining_capacity}
        overAllocation={totals.over_allocation}
      />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MetricTile
          label="Effective capacity"
          value={formatHours(totals.effective_capacity)}
          tooltip={
            <InfoTooltip label="effective capacity">
              Scheduled capacity after availability adjustments for the selected
              period.
            </InfoTooltip>
          }
        />
        <MetricTile
          label="Allocated capacity"
          value={formatHours(totals.allocated_hours)}
          tooltip={
            <InfoTooltip label="allocated capacity">
              Time-phased project demand assigned for the selected period.
            </InfoTooltip>
          }
        />
        <MetricTile
          label="Remaining capacity"
          value={overNote ?? formatHours(totals.remaining_capacity)}
          tone={overNote ? 'danger' : 'success'}
          tooltip={
            <InfoTooltip label="remaining capacity">
              Effective capacity minus allocated capacity. Negative means
              allocated capacity exceeds what's available — shown here as hours
              over capacity.
            </InfoTooltip>
          }
        />
        <MetricTile
          label="Utilization"
          value={formatUtilization(totals.utilization)}
          tooltip={
            <InfoTooltip label="utilization">
              Allocated capacity ÷ effective capacity. Shown as "No effective
              capacity" instead of 0% when there is nothing to divide by, since
              that is a different fact than zero usage.
            </InfoTooltip>
          }
        />
      </div>
    </div>
  )
}

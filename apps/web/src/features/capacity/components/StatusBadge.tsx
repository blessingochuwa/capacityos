import { Badge, type BadgeVariant } from '@/components/ui/Badge'
import {
  AlertIcon,
  CheckCircleIcon,
  DashCircleIcon,
} from '@/components/ui/icons'
import {
  CAPACITY_STATUS_LABEL,
  type CapacityStatus,
} from '../utils/presentation'

const STATUS_VARIANT: Record<CapacityStatus, BadgeVariant> = {
  over: 'danger',
  at: 'info',
  under: 'success',
  'no-data': 'neutral',
}

/** Status is always communicated via this label + icon pair — never color
 * alone (spec §21: "do not rely solely on color"). */
function StatusIcon({ status }: { status: CapacityStatus }) {
  switch (status) {
    case 'over':
      return <AlertIcon />
    case 'at':
      return <DashCircleIcon />
    case 'under':
      return <CheckCircleIcon />
    case 'no-data':
      return null
  }
}

export function StatusBadge({ status }: { status: CapacityStatus }) {
  return (
    <Badge
      variant={STATUS_VARIANT[status]}
      icon={<StatusIcon status={status} />}
    >
      {CAPACITY_STATUS_LABEL[status]}
    </Badge>
  )
}

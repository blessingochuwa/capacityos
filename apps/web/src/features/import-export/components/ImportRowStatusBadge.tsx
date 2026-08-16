import { Badge } from '@/components/ui/Badge'
import {
  ROW_STATUS_BADGE_VARIANT,
  ROW_STATUS_ICON,
  ROW_STATUS_LABEL,
} from '../constants/rowStatus'
import type { ImportRowStatus } from '../types/importExport'

/** Status is always communicated via this label + icon pair — never color
 * alone (CLAUDE.md §21), same pattern as features/insights' SeverityBadge. */
export function ImportRowStatusBadge({
  status,
}: {
  status: ImportRowStatus
}) {
  const Icon = ROW_STATUS_ICON[status]
  return (
    <Badge variant={ROW_STATUS_BADGE_VARIANT[status]} icon={<Icon />}>
      {ROW_STATUS_LABEL[status]}
    </Badge>
  )
}

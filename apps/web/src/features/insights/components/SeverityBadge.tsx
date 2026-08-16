import { Badge } from '@/components/ui/Badge'
import {
  SEVERITY_BADGE_VARIANT,
  SEVERITY_ICON,
  SEVERITY_LABEL,
} from '../constants/severity'
import type { Severity } from '../types/insights'

/** Severity is always communicated via this label + icon pair — never
 * color alone (spec §21), same principle as features/capacity's
 * StatusBadge, extended from 3 to the app's now-4-variant Badge set. */
export function SeverityBadge({ severity }: { severity: Severity }) {
  const Icon = SEVERITY_ICON[severity]
  return (
    <Badge variant={SEVERITY_BADGE_VARIANT[severity]} icon={<Icon />}>
      {SEVERITY_LABEL[severity]}
    </Badge>
  )
}

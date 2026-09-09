import type { BadgeVariant } from '@/components/ui/Badge'
import type { RiskExposure, RiskStatus } from './types/risks'

/** Exposure/status are never conveyed by colour alone (CLAUDE.md §29) —
 * every badge carries its text label too. Extracted from RisksTable.tsx
 * (Phase 47) so the org-wide register (OrgRiskRegisterTable) shares the
 * exact same labels/colours rather than duplicating them. */
export const EXPOSURE_VARIANT: Record<RiskExposure, BadgeVariant> = {
  low: 'neutral',
  medium: 'warning',
  high: 'danger',
}

export const STATUS_LABEL: Record<RiskStatus, string> = {
  open: 'Open',
  mitigating: 'Mitigating',
  monitoring: 'Monitoring',
  closed: 'Closed',
}

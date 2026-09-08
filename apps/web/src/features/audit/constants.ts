import type { BadgeVariant } from '@/components/ui/Badge'
import type { AuditOutcome } from './types/audit'

/** Outcome is never conveyed by colour alone (CLAUDE.md §29) — the badge
 * always carries its text label too. Mirrors features/users/constants.ts's
 * STATUS_BADGE precedent exactly. */
export const OUTCOME_BADGE: Record<AuditOutcome, { variant: BadgeVariant; label: string }> = {
  success: { variant: 'success', label: 'Success' },
  denied: { variant: 'warning', label: 'Denied' },
  failure: { variant: 'danger', label: 'Failure' },
}

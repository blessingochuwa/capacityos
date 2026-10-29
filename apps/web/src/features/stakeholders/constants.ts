import type { BadgeVariant } from '@/components/ui/Badge'
import type { StakeholderDecisionAuthority, StakeholderInfluence } from './types/stakeholders'

/** Influence/interest badges always carry their text label too, never
 * colour alone (CLAUDE.md §29). Extracted from StakeholdersTable.tsx
 * (Phase 48) so the org-wide register (OrgStakeholderRegisterTable)
 * shares the exact same labels/colours rather than duplicating them —
 * the same extraction Phase 47 made for features/risks/constants.ts.
 * Interest reuses this map too: both are the same low/medium/high scale. */
export const INFLUENCE_VARIANT: Record<StakeholderInfluence, BadgeVariant> = {
  low: 'neutral',
  medium: 'info',
  high: 'warning',
}

export const DECISION_AUTHORITY_LABEL: Record<StakeholderDecisionAuthority, string> = {
  decision_maker: 'Decision maker',
  advisor: 'Advisor',
  informed: 'Informed only',
}

export function levelLabel(level: string): string {
  return level.charAt(0).toUpperCase() + level.slice(1)
}

/**
 * Presentation mapping ONLY — no threshold lives here. Unlike
 * features/capacity/constants/thresholds.ts (which holds the one number
 * the frontend itself invents, AT_CAPACITY_MIN), Phase 5 signals arrive
 * pre-classified from the API: severity is the backend's own fact, not a
 * frontend judgment call. See docs/adr/0005-phase-5-operational-insights.md.
 */

import {
  AlertIcon,
  ExclamationCircleIcon,
  InfoIcon,
} from '@/components/ui/icons'
import type { BadgeVariant } from '@/components/ui/Badge'
import type { Severity } from '../types/insights'

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  warning: 'Warning',
  info: 'Info',
}

export const SEVERITY_BADGE_VARIANT: Record<Severity, BadgeVariant> = {
  critical: 'danger',
  warning: 'warning',
  info: 'info',
}

export const SEVERITY_ICON: Record<Severity, typeof AlertIcon> = {
  critical: AlertIcon,
  warning: ExclamationCircleIcon,
  info: InfoIcon,
}

/**
 * Presentation mapping ONLY — every row arrives pre-classified from the API,
 * same principle as features/insights/constants/severity.ts. Never re-derive
 * create/update/unchanged/invalid here.
 */

import {
  AlertIcon,
  CheckCircleIcon,
  DashCircleIcon,
} from '@/components/ui/icons'
import type { BadgeVariant } from '@/components/ui/Badge'
import type { ImportRowStatus } from '../types/importExport'

export const ROW_STATUS_LABEL: Record<ImportRowStatus, string> = {
  valid_create: 'Create',
  valid_update: 'Update',
  valid_unchanged: 'Unchanged',
  invalid: 'Needs fixing',
}

export const ROW_STATUS_BADGE_VARIANT: Record<ImportRowStatus, BadgeVariant> =
  {
    valid_create: 'success',
    valid_update: 'info',
    valid_unchanged: 'neutral',
    invalid: 'danger',
  }

export const ROW_STATUS_ICON: Record<ImportRowStatus, typeof AlertIcon> = {
  valid_create: CheckCircleIcon,
  valid_update: CheckCircleIcon,
  valid_unchanged: DashCircleIcon,
  invalid: AlertIcon,
}

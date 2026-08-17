import type { BadgeVariant } from '@/components/ui/Badge'
import type { AIConfidence } from '../types/ai'

export const CONFIDENCE_LABEL: Record<AIConfidence, string> = {
  high: 'High confidence',
  medium: 'Medium confidence',
  low: 'Low confidence',
}

export const CONFIDENCE_BADGE_VARIANT: Record<AIConfidence, BadgeVariant> = {
  high: 'success',
  medium: 'info',
  low: 'neutral',
}

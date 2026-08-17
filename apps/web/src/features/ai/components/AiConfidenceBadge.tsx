import { Badge } from '@/components/ui/Badge'
import { CONFIDENCE_BADGE_VARIANT, CONFIDENCE_LABEL } from '../constants/confidence'
import type { AIConfidence } from '../types/ai'

export function AiConfidenceBadge({ confidence }: { confidence: AIConfidence }) {
  return (
    <Badge variant={CONFIDENCE_BADGE_VARIANT[confidence]}>
      {CONFIDENCE_LABEL[confidence]}
    </Badge>
  )
}

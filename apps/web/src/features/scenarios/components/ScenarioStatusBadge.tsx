import { Badge, type BadgeVariant } from '@/components/ui/Badge'
import type { ScenarioStatus } from '../types/scenario'

const VARIANT: Record<ScenarioStatus, BadgeVariant> = {
  draft: 'neutral',
  active: 'info',
  archived: 'neutral',
}

const LABEL: Record<ScenarioStatus, string> = {
  draft: 'Draft',
  active: 'Active',
  archived: 'Archived',
}

export function ScenarioStatusBadge({ status }: { status: ScenarioStatus }) {
  return <Badge variant={VARIANT[status]}>{LABEL[status]}</Badge>
}

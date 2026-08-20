import { Badge } from '@/components/ui/Badge'
import type { BadgeVariant } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { RISK_STATUSES } from '../types/risks'
import type { Risk, RiskExposure, RiskStatus } from '../types/risks'

const EXPOSURE_VARIANT: Record<RiskExposure, BadgeVariant> = {
  low: 'neutral',
  medium: 'warning',
  high: 'danger',
}

const STATUS_LABEL: Record<RiskStatus, string> = {
  open: 'Open',
  mitigating: 'Mitigating',
  monitoring: 'Monitoring',
  closed: 'Closed',
}

interface RisksTableProps {
  risks: Risk[]
  personLabels: Map<string, string>
  onStatusChange: (riskId: string, status: RiskStatus) => void
  onRemove: (riskId: string) => void
  updatingId?: string
  removingId?: string
  /** Defaults to true so every existing call site/test keeps its current
   * behavior unless it explicitly opts into role-based gating (see
   * RisksOverviewPage, which passes `can('risk.write')`) — matches
   * SkillsTable's canManage convention. */
  canManage?: boolean
}

export function RisksTable({
  risks,
  personLabels,
  onStatusChange,
  onRemove,
  updatingId,
  removingId,
  canManage = true,
}: RisksTableProps) {
  if (risks.length === 0) {
    return (
      <EmptyState
        title="No risks recorded for this project yet."
        description="Add a risk below to start tracking it — CapacityOS never invents or scores risks automatically."
      />
    )
  }

  return (
    <Table caption="Risks recorded for this project, their exposure, and their status">
      <thead>
        <tr>
          <Th scope="col">Risk</Th>
          <Th scope="col">Exposure</Th>
          <Th scope="col">Owner</Th>
          <Th scope="col">Status</Th>
          <Th scope="col">Review date</Th>
          <Th scope="col">
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {risks.map((risk) => (
          <tr key={risk.id}>
            <Td>
              <div className="font-medium text-slate-100">{risk.description}</div>
              {risk.potential_effect ? (
                <div className="text-xs text-slate-400">{risk.potential_effect}</div>
              ) : null}
            </Td>
            <Td>
              <Badge variant={EXPOSURE_VARIANT[risk.exposure]}>
                {risk.exposure.charAt(0).toUpperCase() + risk.exposure.slice(1)}
              </Badge>
            </Td>
            <Td>
              {risk.owner_person_id
                ? (personLabels.get(risk.owner_person_id) ?? 'Unknown')
                : 'Unassigned'}
            </Td>
            <Td>
              {canManage ? (
                <select
                  aria-label={`Status for ${risk.description}`}
                  value={risk.status}
                  disabled={updatingId === risk.id}
                  onChange={(event) =>
                    onStatusChange(risk.id, event.target.value as RiskStatus)
                  }
                  className="w-36 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
                >
                  {RISK_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {STATUS_LABEL[status]}
                    </option>
                  ))}
                </select>
              ) : (
                <Badge variant={risk.status === 'closed' ? 'neutral' : 'info'}>
                  {STATUS_LABEL[risk.status]}
                </Badge>
              )}
            </Td>
            <Td>{risk.review_date ?? '—'}</Td>
            <Td>
              {canManage ? (
                <Button
                  variant="ghost"
                  onClick={() => onRemove(risk.id)}
                  disabled={removingId === risk.id}
                >
                  {removingId === risk.id ? 'Removing…' : 'Remove'}
                </Button>
              ) : null}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

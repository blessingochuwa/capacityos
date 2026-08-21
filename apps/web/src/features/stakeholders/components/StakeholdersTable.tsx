import { Badge } from '@/components/ui/Badge'
import type { BadgeVariant } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import type { Stakeholder, StakeholderInfluence } from '../types/stakeholders'

const INFLUENCE_VARIANT: Record<StakeholderInfluence, BadgeVariant> = {
  low: 'neutral',
  medium: 'info',
  high: 'warning',
}

const DECISION_AUTHORITY_LABEL: Record<Stakeholder['decision_authority'], string> = {
  decision_maker: 'Decision maker',
  advisor: 'Advisor',
  informed: 'Informed only',
}

interface StakeholdersTableProps {
  stakeholders: Stakeholder[]
  personLabels: Map<string, string>
  onEdit: (stakeholderId: string) => void
  onRemove: (stakeholderId: string) => void
  editingId?: string
  removingId?: string
  /** Defaults to true so every existing call site/test keeps its current
   * behavior unless it explicitly opts into role-based gating (see
   * StakeholdersOverviewPage, which passes `can('stakeholder.write')`) —
   * matches RisksTable/SkillsTable's canManage convention. */
  canManage?: boolean
}

export function StakeholdersTable({
  stakeholders,
  personLabels,
  onEdit,
  onRemove,
  editingId,
  removingId,
  canManage = true,
}: StakeholdersTableProps) {
  if (stakeholders.length === 0) {
    return (
      <EmptyState
        title="No stakeholders recorded for this project yet."
        description="Add a stakeholder below to start tracking who needs to be engaged and how."
      />
    )
  }

  return (
    <Table caption="Stakeholders recorded for this project, their influence, interest, and decision authority">
      <thead>
        <tr>
          <Th scope="col">Stakeholder</Th>
          <Th scope="col">Role</Th>
          <Th scope="col">Influence</Th>
          <Th scope="col">Interest</Th>
          <Th scope="col">Decision authority</Th>
          <Th scope="col">
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {stakeholders.map((stakeholder) => (
          <tr key={stakeholder.id}>
            <Td>
              <div className="font-medium text-slate-100">{stakeholder.name}</div>
              {stakeholder.person_id ? (
                <div className="text-xs text-slate-400">
                  Linked to {personLabels.get(stakeholder.person_id) ?? 'Unknown person'}
                </div>
              ) : null}
              {stakeholder.communication_needs ? (
                <div className="text-xs text-slate-400">{stakeholder.communication_needs}</div>
              ) : null}
            </Td>
            <Td>{stakeholder.role}</Td>
            <Td>
              <Badge variant={INFLUENCE_VARIANT[stakeholder.influence]}>
                {stakeholder.influence.charAt(0).toUpperCase() + stakeholder.influence.slice(1)}
              </Badge>
            </Td>
            <Td>
              <Badge variant={INFLUENCE_VARIANT[stakeholder.interest]}>
                {stakeholder.interest.charAt(0).toUpperCase() + stakeholder.interest.slice(1)}
              </Badge>
            </Td>
            <Td>{DECISION_AUTHORITY_LABEL[stakeholder.decision_authority]}</Td>
            <Td>
              {canManage ? (
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => onEdit(stakeholder.id)}
                    disabled={editingId === stakeholder.id}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => onRemove(stakeholder.id)}
                    disabled={removingId === stakeholder.id}
                  >
                    {removingId === stakeholder.id ? 'Removing…' : 'Remove'}
                  </Button>
                </div>
              ) : null}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

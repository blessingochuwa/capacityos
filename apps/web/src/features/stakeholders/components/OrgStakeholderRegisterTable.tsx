import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { DECISION_AUTHORITY_LABEL, INFLUENCE_VARIANT, levelLabel } from '../constants'
import type { Stakeholder } from '../types/stakeholders'

interface OrgStakeholderRegisterTableProps {
  stakeholders: Stakeholder[]
  /** project_id -> display name. A stakeholder whose project_id isn't in
   * this map (e.g. the project list is still loading) shows a placeholder
   * rather than a blank cell. */
  projectLabels: Map<string, string>
  personLabels: Map<string, string>
  /** True when any filter is applied — an empty result then means "no
   * match," not "nothing recorded" (OrgRiskRegisterTable's precedent). */
  isFiltered?: boolean
}

/** The org-wide Stakeholder register's read-only list (Phase 48) — every
 * field GET /api/v1/stakeholders already returns, plus the project name
 * joined client-side. Reuses StakeholdersTable's badge styling
 * (features/stakeholders/constants.ts) so both views agree on what a
 * badge means. Deliberately no Edit/Remove controls — this is a register;
 * StakeholdersTable remains the per-project management surface. */
export function OrgStakeholderRegisterTable({
  stakeholders,
  projectLabels,
  personLabels,
  isFiltered = false,
}: OrgStakeholderRegisterTableProps) {
  if (stakeholders.length === 0) {
    return isFiltered ? (
      <EmptyState
        title="No stakeholders match these filters."
        description="Try a different project, influence, interest, or decision authority."
      />
    ) : (
      <EmptyState
        title="No stakeholders recorded in this organization yet."
        description="Record a stakeholder from a project's register above to see it here."
      />
    )
  }

  return (
    <Table caption="Every stakeholder across every project in this organization">
      <thead>
        <tr>
          <Th scope="col">Project</Th>
          <Th scope="col">Stakeholder</Th>
          <Th scope="col">Role</Th>
          <Th scope="col">Influence</Th>
          <Th scope="col">Interest</Th>
          <Th scope="col">Decision authority</Th>
        </tr>
      </thead>
      <tbody>
        {stakeholders.map((stakeholder) => (
          <tr key={stakeholder.id}>
            <Td className="font-medium text-slate-100">
              {projectLabels.get(stakeholder.project_id) ?? 'Unknown project'}
            </Td>
            <Td>
              <div className="text-slate-200">{stakeholder.name}</div>
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
                {levelLabel(stakeholder.influence)}
              </Badge>
            </Td>
            <Td>
              <Badge variant={INFLUENCE_VARIANT[stakeholder.interest]}>
                {levelLabel(stakeholder.interest)}
              </Badge>
            </Td>
            <Td>{DECISION_AUTHORITY_LABEL[stakeholder.decision_authority]}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

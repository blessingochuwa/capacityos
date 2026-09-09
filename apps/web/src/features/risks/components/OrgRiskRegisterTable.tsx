import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { EXPOSURE_VARIANT, STATUS_LABEL } from '../constants'
import type { Risk } from '../types/risks'

interface OrgRiskRegisterTableProps {
  risks: Risk[]
  /** project_id -> display name, for every project this table might show
   * a row for. A risk whose project_id isn't in this map (e.g. the
   * project list is still loading) falls back to a placeholder rather
   * than a blank cell. */
  projectLabels: Map<string, string>
  personLabels: Map<string, string>
  /** True when a project/status/exposure filter is currently applied —
   * an empty result then means "no match," not "no risk history exists"
   * (mirrors features/audit/components/AuditEventsTable.tsx's
   * `isFiltered` precedent). */
  isFiltered?: boolean
}

/** The org-wide Risk register's read-only list (Phase 47) — every field
 * already returned by GET /api/v1/risks, reusing RisksTable's own
 * exposure/status badge styling (features/risks/constants.ts) so the two
 * views never disagree about what a badge means. Deliberately no status
 * control, no owner reassignment, no remove button — this is a register,
 * not the per-project management surface RisksTable already is. */
export function OrgRiskRegisterTable({
  risks,
  projectLabels,
  personLabels,
  isFiltered = false,
}: OrgRiskRegisterTableProps) {
  if (risks.length === 0) {
    return isFiltered ? (
      <EmptyState
        title="No risks match these filters."
        description="Try a different project, status, or exposure level."
      />
    ) : (
      <EmptyState
        title="No risks recorded in this organization yet."
        description="Record a risk from a project's own Risks page to see it here."
      />
    )
  }

  return (
    <Table caption="Every risk across every project in this organization">
      <thead>
        <tr>
          <Th scope="col">Project</Th>
          <Th scope="col">Risk</Th>
          <Th scope="col">Exposure</Th>
          <Th scope="col">Owner</Th>
          <Th scope="col">Status</Th>
          <Th scope="col">Review date</Th>
        </tr>
      </thead>
      <tbody>
        {risks.map((risk) => (
          <tr key={risk.id}>
            <Td className="font-medium text-slate-100">
              {projectLabels.get(risk.project_id) ?? 'Unknown project'}
            </Td>
            <Td>
              <div className="text-slate-200">{risk.description}</div>
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
              <Badge variant={risk.status === 'closed' ? 'neutral' : 'info'}>
                {STATUS_LABEL[risk.status]}
              </Badge>
            </Td>
            <Td>{risk.review_date ?? '—'}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { formatHours, formatUtilization } from '@/features/capacity/utils/presentation'
import { toNumber } from '@/lib/decimal'
import type { SkillCoverage } from '../types/skills'

interface ProjectSkillCoverageTableProps {
  requirements: SkillCoverage[]
  onRemove: (requirementId: string) => void
  removingId?: string
}

/** Distinguishes fully covered / partially covered / uncovered by an
 * objective fact (gap_hours vs qualified_available_hours), never a color
 * alone — CLAUDE.md §21/§29. Requirements existing at all vs being empty is
 * the caller's job (see ProjectSkillCoverage.requirements === []). */
function coverageBadge(requirement: SkillCoverage): { variant: 'success' | 'warning' | 'danger'; label: string } {
  if (toNumber(requirement.gap_hours) === 0) {
    return { variant: 'success', label: 'Fully covered' }
  }
  if (toNumber(requirement.qualified_available_hours) === 0) {
    return { variant: 'danger', label: 'Uncovered' }
  }
  return { variant: 'warning', label: 'Partially covered' }
}

export function ProjectSkillCoverageTable({
  requirements,
  onRemove,
  removingId,
}: ProjectSkillCoverageTableProps) {
  if (requirements.length === 0) {
    return (
      <EmptyState
        title="No skill requirements configured for this project."
        description="Add a requirement below to see qualified capacity and coverage against it."
      />
    )
  }

  return (
    <Table caption="Required skills, qualified available capacity, and coverage for this project">
      <thead>
        <tr>
          <Th scope="col">Skill</Th>
          <Th scope="col">Required</Th>
          <Th scope="col">Qualified available</Th>
          <Th scope="col">Gap</Th>
          <Th scope="col">Coverage</Th>
          <Th scope="col">Qualified people</Th>
          <Th scope="col">
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {requirements.map((requirement) => {
          const status = coverageBadge(requirement)
          return (
            <tr key={requirement.requirement_id}>
              <Td>
                <div className="font-medium text-slate-100">{requirement.skill_label}</div>
                {requirement.minimum_proficiency ? (
                  <div className="text-xs text-slate-400">
                    Min. proficiency: {requirement.minimum_proficiency}
                  </div>
                ) : null}
              </Td>
              <Td>{formatHours(requirement.required_hours)}</Td>
              <Td>{formatHours(requirement.qualified_available_hours)}</Td>
              <Td>{formatHours(requirement.gap_hours)}</Td>
              <Td>
                <div className="flex items-center gap-2">
                  <Badge variant={status.variant}>{status.label}</Badge>
                  <span className="text-xs text-slate-400">
                    {formatUtilization(requirement.coverage_ratio)}
                  </span>
                </div>
              </Td>
              <Td>
                {requirement.qualified_people.length === 0
                  ? '—'
                  : requirement.qualified_people
                      .map((person) => `${person.person_label} (${person.proficiency})`)
                      .join(', ')}
              </Td>
              <Td>
                <Button
                  variant="ghost"
                  onClick={() => onRemove(requirement.requirement_id)}
                  disabled={removingId === requirement.requirement_id}
                >
                  {removingId === requirement.requirement_id ? 'Removing…' : 'Remove'}
                </Button>
              </Td>
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}

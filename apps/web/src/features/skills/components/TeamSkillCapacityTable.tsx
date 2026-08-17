import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { formatHours } from '@/features/capacity/utils/presentation'
import type { TeamSkillCapacityEntry } from '../types/skills'

interface TeamSkillCapacityTableProps {
  skills: TeamSkillCapacityEntry[]
}

/** Supply only — no "required hours" column. A team has no stored skill
 * demand of its own; only a Project's ProjectSkillRequirement carries one
 * (see docs/adr/0007-phase-7-skills-bottleneck-analysis.md). */
export function TeamSkillCapacityTable({ skills }: TeamSkillCapacityTableProps) {
  if (skills.length === 0) {
    return (
      <EmptyState
        title="No team member currently holds a recorded skill."
        description="Record skills on individual people to see this team's qualified capacity by skill."
      />
    )
  }

  return (
    <Table caption="Qualified available capacity by skill for this team's members">
      <thead>
        <tr>
          <Th scope="col">Skill</Th>
          <Th scope="col">Qualified available capacity</Th>
          <Th scope="col">People with this skill</Th>
        </tr>
      </thead>
      <tbody>
        {skills.map((entry) => (
          <tr key={entry.skill_id}>
            <Td className="font-medium text-slate-100">{entry.skill_label}</Td>
            <Td>{formatHours(entry.qualified_available_hours)}</Td>
            <Td>
              {entry.qualified_people
                .map((person) => `${person.person_label} (${person.proficiency})`)
                .join(', ')}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

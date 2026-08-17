import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import type { Skill } from '../types/skills'

interface SkillsTableProps {
  skills: Skill[]
  onDeactivate: (skillId: string) => void
  deactivatingId?: string
}

export function SkillsTable({
  skills,
  onDeactivate,
  deactivatingId,
}: SkillsTableProps) {
  if (skills.length === 0) {
    return (
      <EmptyState
        title="No skills defined yet."
        description="Add a skill above to start recording who holds it and which projects require it."
      />
    )
  }

  return (
    <Table caption="Skills, their category, and how many people hold them">
      <thead>
        <tr>
          <Th scope="col">Skill</Th>
          <Th scope="col">Category</Th>
          <Th scope="col">People</Th>
          <Th scope="col">Status</Th>
          <Th scope="col">
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {skills.map((skill) => (
          <tr key={skill.id}>
            <Td>
              <div className="font-medium text-slate-100">{skill.name}</div>
              {skill.description ? (
                <div className="text-xs text-slate-400">{skill.description}</div>
              ) : null}
            </Td>
            <Td>{skill.category ?? '—'}</Td>
            <Td>{skill.person_count}</Td>
            <Td>
              <Badge variant={skill.is_active ? 'success' : 'neutral'}>
                {skill.is_active ? 'Active' : 'Inactive'}
              </Badge>
            </Td>
            <Td>
              {skill.is_active ? (
                <Button
                  variant="ghost"
                  onClick={() => onDeactivate(skill.id)}
                  disabled={deactivatingId === skill.id}
                >
                  {deactivatingId === skill.id ? 'Deactivating…' : 'Deactivate'}
                </Button>
              ) : null}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

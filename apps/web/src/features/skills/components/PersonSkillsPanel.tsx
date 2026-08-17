import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { Skeleton } from '@/components/ui/Skeleton'
import { usePersonSkills, useAddPersonSkill, useRemovePersonSkill } from '../hooks/usePersonSkills'
import { useSkills } from '../hooks/useSkills'
import { SkillPicker } from './SkillPicker'
import { ProficiencySelect } from './ProficiencySelect'
import type { SkillProficiency } from '../types/skills'

interface PersonSkillsPanelProps {
  personId: string
}

export function PersonSkillsPanel({ personId }: PersonSkillsPanelProps) {
  const personSkillsQuery = usePersonSkills(personId)
  const skillsQuery = useSkills()
  const addPersonSkill = useAddPersonSkill(personId)
  const removePersonSkill = useRemovePersonSkill(personId)
  const [skillId, setSkillId] = useState<string | undefined>(undefined)
  const [proficiency, setProficiency] = useState<SkillProficiency | ''>('')

  if (personSkillsQuery.isPending || skillsQuery.isPending) {
    return <Skeleton className="h-24" />
  }
  if (personSkillsQuery.isError) {
    return (
      <ErrorState
        error={personSkillsQuery.error}
        onRetry={() => void personSkillsQuery.refetch()}
      />
    )
  }
  if (skillsQuery.isError || !skillsQuery.data) {
    return (
      <ErrorState error={skillsQuery.error} onRetry={() => void skillsQuery.refetch()} />
    )
  }

  const skillLabels = new Map(
    skillsQuery.data.items.map((skill) => [skill.id, skill.name]),
  )
  const personSkills = personSkillsQuery.data ?? []
  const heldSkillIds = personSkills.map((row) => row.skill_id)

  function handleAdd(event: React.FormEvent) {
    event.preventDefault()
    if (!skillId || !proficiency) return
    addPersonSkill.mutate(
      { skill_id: skillId, proficiency },
      { onSuccess: () => { setSkillId(undefined); setProficiency('') } },
    )
  }

  return (
    <div className="space-y-4">
      {personSkills.length === 0 ? (
        <EmptyState
          title="No skills recorded for this person yet."
          description="Skills are added explicitly — never inferred from job title or allocation history."
        />
      ) : (
        <ul className="flex flex-wrap gap-2">
          {personSkills.map((row) => (
            <li key={row.id}>
              <Badge variant="info">
                {skillLabels.get(row.skill_id) ?? 'Unknown skill'} · {row.proficiency}
                <button
                  type="button"
                  onClick={() => removePersonSkill.mutate(row.id)}
                  aria-label={`Remove ${skillLabels.get(row.skill_id) ?? 'skill'}`}
                  className="ml-1 text-slate-400 hover:text-slate-200"
                >
                  ×
                </button>
              </Badge>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleAdd} className="flex flex-wrap items-end gap-3">
        <div className="w-56">
          <SkillPicker
            value={skillId}
            onChange={setSkillId}
            excludeSkillIds={heldSkillIds}
          />
        </div>
        <div className="w-40">
          <ProficiencySelect
            value={proficiency}
            onChange={setProficiency}
            placeholder="Select level"
          />
        </div>
        <Button
          type="submit"
          variant="primary"
          disabled={!skillId || !proficiency || addPersonSkill.isPending}
        >
          {addPersonSkill.isPending ? 'Adding…' : 'Add skill'}
        </Button>
      </form>
      {addPersonSkill.isError ? (
        <p role="alert" className="text-xs text-rose-300">
          {addPersonSkill.error.message}
        </p>
      ) : null}
    </div>
  )
}

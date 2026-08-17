import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useAddProjectSkillRequirement } from '../hooks/useProjectSkillRequirements'
import { SkillPicker } from './SkillPicker'
import { ProficiencySelect } from './ProficiencySelect'
import type { SkillProficiency } from '../types/skills'

interface ProjectSkillRequirementFormProps {
  projectId: string
  excludeSkillIds: string[]
}

export function ProjectSkillRequirementForm({
  projectId,
  excludeSkillIds,
}: ProjectSkillRequirementFormProps) {
  const [skillId, setSkillId] = useState<string | undefined>(undefined)
  const [hours, setHours] = useState('')
  const [minimumProficiency, setMinimumProficiency] = useState<SkillProficiency | ''>('')
  const addRequirement = useAddProjectSkillRequirement(projectId)

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!skillId || !hours) return
    addRequirement.mutate(
      {
        skill_id: skillId,
        required_hours: hours,
        minimum_proficiency: minimumProficiency || undefined,
      },
      {
        onSuccess: () => {
          setSkillId(undefined)
          setHours('')
          setMinimumProficiency('')
        },
      },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div className="w-56">
        <SkillPicker value={skillId} onChange={setSkillId} excludeSkillIds={excludeSkillIds} />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="requirement-hours" className="text-xs font-medium text-slate-400">
          Required hours
        </label>
        <input
          id="requirement-hours"
          type="number"
          min="0.01"
          step="0.01"
          value={hours}
          onChange={(event) => setHours(event.target.value)}
          className="w-28 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
        />
      </div>
      <div className="w-40">
        <ProficiencySelect
          label="Min. proficiency"
          value={minimumProficiency}
          onChange={setMinimumProficiency}
          placeholder="Any"
        />
      </div>
      <Button
        type="submit"
        variant="primary"
        disabled={!skillId || !hours || addRequirement.isPending}
      >
        {addRequirement.isPending ? 'Adding…' : 'Add requirement'}
      </Button>
      {addRequirement.isError ? (
        <p role="alert" className="text-xs text-rose-300">
          {addRequirement.error.message}
        </p>
      ) : null}
    </form>
  )
}

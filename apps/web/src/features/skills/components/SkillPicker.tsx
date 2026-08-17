import { Select } from '@/components/ui/Select'
import { useSkills } from '../hooks/useSkills'

interface SkillPickerProps {
  value: string | undefined
  onChange: (skillId: string) => void
  excludeSkillIds?: string[]
}

/** Active skills only — a deactivated skill can't be newly assigned to a
 * person or required by a project (see SkillService.deactivate's docstring
 * on the backend). */
export function SkillPicker({
  value,
  onChange,
  excludeSkillIds = [],
}: SkillPickerProps) {
  const { data, isPending, isError } = useSkills(true)

  if (isPending || isError || !data) {
    return (
      <Select
        label="Skill"
        options={[]}
        placeholder={isError ? "Couldn't load skills" : 'Loading skills…'}
        disabled
        value=""
        onChange={() => {}}
      />
    )
  }

  const options = data.items
    .filter((skill) => !excludeSkillIds.includes(skill.id))
    .map((skill) => ({ value: skill.id, label: skill.name }))

  return (
    <Select
      label="Skill"
      value={value ?? ''}
      placeholder={options.length === 0 ? 'No skills available' : 'Select a skill'}
      options={options}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

import { Select } from '@/components/ui/Select'
import { SKILL_PROFICIENCY_LEVELS } from '../types/skills'
import type { SkillProficiency } from '../types/skills'

interface ProficiencySelectProps {
  label?: string
  value: SkillProficiency | ''
  onChange: (proficiency: SkillProficiency) => void
  placeholder?: string
}

export function ProficiencySelect({
  label = 'Proficiency',
  value,
  onChange,
  placeholder,
}: ProficiencySelectProps) {
  return (
    <Select
      label={label}
      value={value}
      placeholder={placeholder}
      options={SKILL_PROFICIENCY_LEVELS.map((level) => ({
        value: level,
        label: level.charAt(0).toUpperCase() + level.slice(1),
      }))}
      onChange={(event) => onChange(event.target.value as SkillProficiency)}
    />
  )
}

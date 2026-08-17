/**
 * Mirrors apps/api/app/schemas/skill.py, person_skill.py,
 * project_skill_requirement.py, and skill_capacity.py verbatim. Qualified
 * capacity/coverage numbers arrive pre-computed from the API — nothing here
 * recalculates them (CLAUDE.md §4; see
 * docs/adr/0007-phase-7-skills-bottleneck-analysis.md).
 */

export type SkillProficiency =
  | 'beginner'
  | 'working'
  | 'proficient'
  | 'advanced'
  | 'expert'

export const SKILL_PROFICIENCY_LEVELS: SkillProficiency[] = [
  'beginner',
  'working',
  'proficient',
  'advanced',
  'expert',
]

export interface Skill {
  id: string
  name: string
  description: string | null
  category: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  person_count: number
}

export interface PersonSkill {
  id: string
  person_id: string
  skill_id: string
  proficiency: SkillProficiency
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ProjectSkillRequirement {
  id: string
  project_id: string
  skill_id: string
  required_hours: string
  minimum_proficiency: SkillProficiency | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface QualifiedPerson {
  person_id: string
  person_label: string
  proficiency: SkillProficiency
  qualified_available_hours: string
}

export interface SkillCoverage {
  requirement_id: string
  skill_id: string
  skill_label: string
  required_hours: string
  minimum_proficiency: SkillProficiency | null
  qualified_available_hours: string
  coverage_ratio: string
  gap_hours: string
  qualified_people: QualifiedPerson[]
}

export interface ProjectSkillCoverage {
  project_id: string
  project_label: string
  start_date: string
  end_date: string
  requirements: SkillCoverage[]
}

export interface TeamSkillCapacityEntry {
  skill_id: string
  skill_label: string
  qualified_available_hours: string
  qualified_people: QualifiedPerson[]
}

export interface TeamSkillCapacity {
  team_id: string
  team_label: string
  start_date: string
  end_date: string
  skills: TeamSkillCapacityEntry[]
}

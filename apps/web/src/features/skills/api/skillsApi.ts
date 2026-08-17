import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import type { Page } from '@/types/entities'
import type {
  PersonSkill,
  ProjectSkillCoverage,
  ProjectSkillRequirement,
  Skill,
  SkillProficiency,
  TeamSkillCapacity,
} from '../types/skills'

const LIST_ALL_LIMIT = 500

export interface DateRangeParams {
  start_date: string
  end_date: string
}

export interface SkillCreateInput {
  name: string
  description?: string
  category?: string
}

export interface SkillUpdateInput {
  name?: string
  description?: string
  category?: string
  is_active?: boolean
}

export interface PersonSkillInput {
  skill_id: string
  proficiency: SkillProficiency
  notes?: string
}

export interface ProjectSkillRequirementInput {
  skill_id: string
  required_hours: string
  minimum_proficiency?: SkillProficiency
  notes?: string
}

export const skillsApi = {
  list: (isActive?: boolean) =>
    apiGet<Page<Skill>>('/api/v1/skills', {
      limit: LIST_ALL_LIMIT,
      ...(isActive !== undefined ? { is_active: String(isActive) } : {}),
    }),
  get: (skillId: string) => apiGet<Skill>(`/api/v1/skills/${skillId}`),
  create: (data: SkillCreateInput) => apiPost<Skill>('/api/v1/skills', data),
  update: (skillId: string, data: SkillUpdateInput) =>
    apiPatch<Skill>(`/api/v1/skills/${skillId}`, data),
  deactivate: (skillId: string) => apiDelete(`/api/v1/skills/${skillId}`),

  listPersonSkills: (personId: string) =>
    apiGet<PersonSkill[]>(`/api/v1/people/${personId}/skills`),
  addPersonSkill: (personId: string, data: PersonSkillInput) =>
    apiPost<PersonSkill>(`/api/v1/people/${personId}/skills`, data),
  updatePersonSkill: (
    personId: string,
    personSkillId: string,
    data: { proficiency?: SkillProficiency; notes?: string },
  ) =>
    apiPatch<PersonSkill>(
      `/api/v1/people/${personId}/skills/${personSkillId}`,
      data,
    ),
  removePersonSkill: (personId: string, personSkillId: string) =>
    apiDelete(`/api/v1/people/${personId}/skills/${personSkillId}`),

  listProjectSkillRequirements: (projectId: string) =>
    apiGet<ProjectSkillRequirement[]>(
      `/api/v1/projects/${projectId}/skill-requirements`,
    ),
  addProjectSkillRequirement: (
    projectId: string,
    data: ProjectSkillRequirementInput,
  ) =>
    apiPost<ProjectSkillRequirement>(
      `/api/v1/projects/${projectId}/skill-requirements`,
      data,
    ),
  updateProjectSkillRequirement: (
    projectId: string,
    requirementId: string,
    data: Partial<ProjectSkillRequirementInput>,
  ) =>
    apiPatch<ProjectSkillRequirement>(
      `/api/v1/projects/${projectId}/skill-requirements/${requirementId}`,
      data,
    ),
  removeProjectSkillRequirement: (projectId: string, requirementId: string) =>
    apiDelete(
      `/api/v1/projects/${projectId}/skill-requirements/${requirementId}`,
    ),

  getProjectSkillCoverage: (projectId: string, range: DateRangeParams) =>
    apiGet<ProjectSkillCoverage>(
      `/api/v1/projects/${projectId}/skill-coverage`,
      { ...range },
    ),
  getTeamSkillCapacity: (teamId: string, range: DateRangeParams) =>
    apiGet<TeamSkillCapacity>(`/api/v1/teams/${teamId}/skill-capacity`, {
      ...range,
    }),
}

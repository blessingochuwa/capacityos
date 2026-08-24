import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import type { Page } from '@/types/entities'
import type {
  PortfolioRanking,
  PrioritizationFramework,
  PrioritizationFrameworkType,
  ProjectPriorityScore,
} from '../types/prioritization'

export interface CriterionInput {
  name: string
  weight: string
}

export interface FrameworkCreateInput {
  name: string
  framework_type: PrioritizationFrameworkType
  criteria: CriterionInput[]
}

export interface FrameworkUpdateInput {
  name?: string
  is_active?: boolean
}

export interface CriterionValueInput {
  criterion_key: string
  value: string
}

export interface ScoreCreateInput {
  framework_id: string
  values: CriterionValueInput[]
  notes?: string | null
}

export interface ScoreUpdateInput {
  values?: CriterionValueInput[]
  notes?: string | null
}

export const prioritizationApi = {
  listFrameworks: (isActive?: boolean) =>
    apiGet<Page<PrioritizationFramework>>('/api/v1/prioritization/frameworks', {
      is_active: isActive === undefined ? undefined : String(isActive),
    }),
  createFramework: (data: FrameworkCreateInput) =>
    apiPost<PrioritizationFramework>('/api/v1/prioritization/frameworks', data),
  updateFramework: (frameworkId: string, data: FrameworkUpdateInput) =>
    apiPatch<PrioritizationFramework>(
      `/api/v1/prioritization/frameworks/${frameworkId}`,
      data,
    ),
  deactivateFramework: (frameworkId: string) =>
    apiDelete<PrioritizationFramework>(`/api/v1/prioritization/frameworks/${frameworkId}`),

  rankPortfolio: (frameworkId: string) =>
    apiGet<PortfolioRanking>('/api/v1/prioritization/portfolio', { framework_id: frameworkId }),

  listScoresForProject: (projectId: string) =>
    apiGet<ProjectPriorityScore[]>(`/api/v1/projects/${projectId}/priority-scores`),
  createScore: (projectId: string, data: ScoreCreateInput) =>
    apiPost<ProjectPriorityScore>(`/api/v1/projects/${projectId}/priority-scores`, data),
  updateScore: (projectId: string, scoreId: string, data: ScoreUpdateInput) =>
    apiPatch<ProjectPriorityScore>(
      `/api/v1/projects/${projectId}/priority-scores/${scoreId}`,
      data,
    ),
  deleteScore: (projectId: string, scoreId: string) =>
    apiDelete(`/api/v1/projects/${projectId}/priority-scores/${scoreId}`),
}

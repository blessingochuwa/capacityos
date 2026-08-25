import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import type { Page } from '@/types/entities'
import type {
  DependencyGraph,
  MoscowCategory,
  PortfolioRanking,
  PortfolioSnapshot,
  PortfolioSnapshotComparison,
  PrioritizationCriterion,
  PrioritizationFramework,
  PrioritizationFrameworkType,
  ProjectDependency,
  ProjectDependencyType,
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

export interface CriterionUpdateInput {
  name?: string
  weight?: string
}

export interface CriterionValueInput {
  criterion_key: string
  value: string
}

export interface ScoreCreateInput {
  framework_id: string
  values: CriterionValueInput[]
  category?: MoscowCategory | null
  notes?: string | null
}

export interface ScoreUpdateInput {
  values?: CriterionValueInput[]
  category?: MoscowCategory | null
  notes?: string | null
}

export interface DependencyCreateInput {
  to_project_id: string
  dependency_type: ProjectDependencyType
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

  addCriterion: (frameworkId: string, data: CriterionInput) =>
    apiPost<PrioritizationCriterion>(
      `/api/v1/prioritization/frameworks/${frameworkId}/criteria`,
      data,
    ),
  updateCriterion: (frameworkId: string, criterionId: string, data: CriterionUpdateInput) =>
    apiPatch<PrioritizationCriterion>(
      `/api/v1/prioritization/frameworks/${frameworkId}/criteria/${criterionId}`,
      data,
    ),
  removeCriterion: (frameworkId: string, criterionId: string) =>
    apiDelete(`/api/v1/prioritization/frameworks/${frameworkId}/criteria/${criterionId}`),

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

  listDependenciesForProject: (projectId: string) =>
    apiGet<ProjectDependency[]>(`/api/v1/projects/${projectId}/dependencies`),
  createDependency: (projectId: string, data: DependencyCreateInput) =>
    apiPost<ProjectDependency>(`/api/v1/projects/${projectId}/dependencies`, data),
  deleteDependency: (projectId: string, dependencyId: string) =>
    apiDelete(`/api/v1/projects/${projectId}/dependencies/${dependencyId}`),
  getDependencyGraph: () =>
    apiGet<DependencyGraph>('/api/v1/prioritization/dependency-graph'),

  listSnapshots: (frameworkId?: string) =>
    apiGet<Page<PortfolioSnapshot>>('/api/v1/prioritization/snapshots', {
      framework_id: frameworkId,
    }),
  createSnapshot: (frameworkId: string) =>
    apiPost<PortfolioSnapshot>('/api/v1/prioritization/snapshots', {
      framework_id: frameworkId,
    }),
  compareSnapshots: (fromSnapshotId: string, toSnapshotId: string) =>
    apiGet<PortfolioSnapshotComparison>('/api/v1/prioritization/snapshots/compare', {
      from_snapshot_id: fromSnapshotId,
      to_snapshot_id: toSnapshotId,
    }),
}

import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/client'
import type { Page } from '@/types/entities'
import type { MoscowCategory } from '@/features/prioritization/types/prioritization'
import type {
  Scenario,
  ScenarioComparison,
  ScenarioOperation,
  ScenarioOperationPayload,
  ScenarioResults,
  ScenarioStatus,
} from '../types/scenario'
import type {
  ScenarioPriorityComparison,
  ScenarioPriorityOverride,
} from '../types/scenarioPriority'

/** Typed wrappers over apps/api's scenario endpoints
 * (apps/api/app/api/v1/scenarios.py). Unlike features/capacity/api, this
 * module writes — creating/editing a scenario or its operations never
 * touches production data (CLAUDE.md §19); only /calculate reads current
 * baseline data to compute a hypothetical result. */

const LIST_ALL_LIMIT = 500

export interface ScenarioCreateInput {
  name: string
  description?: string | null
  baseline_start_date: string
  baseline_end_date: string
  created_by?: string | null
}

export interface ScenarioUpdateInput {
  name?: string
  description?: string | null
  status?: ScenarioStatus
  baseline_start_date?: string
  baseline_end_date?: string
}

export interface ScenarioPriorityOverrideCriterionInput {
  criterion_key: string
  value: string
}

export interface ScenarioPriorityOverrideSetInput {
  project_id: string
  framework_id: string
  values?: ScenarioPriorityOverrideCriterionInput[]
  category?: MoscowCategory | null
}

export const scenariosApi = {
  list: (status?: ScenarioStatus) =>
    apiGet<Page<Scenario>>('/api/v1/scenarios', {
      status,
      limit: LIST_ALL_LIMIT,
    }),

  get: (scenarioId: string) =>
    apiGet<Scenario>(`/api/v1/scenarios/${scenarioId}`),

  create: (data: ScenarioCreateInput) =>
    apiPost<Scenario>('/api/v1/scenarios', data),

  update: (scenarioId: string, data: ScenarioUpdateInput) =>
    apiPatch<Scenario>(`/api/v1/scenarios/${scenarioId}`, data),

  remove: (scenarioId: string) =>
    apiDelete<void>(`/api/v1/scenarios/${scenarioId}`),

  listOperations: (scenarioId: string) =>
    apiGet<Page<ScenarioOperation>>(
      `/api/v1/scenarios/${scenarioId}/operations`,
      {
        limit: LIST_ALL_LIMIT,
      },
    ),

  createOperation: (scenarioId: string, payload: ScenarioOperationPayload) =>
    apiPost<ScenarioOperation>(
      `/api/v1/scenarios/${scenarioId}/operations`,
      payload,
    ),

  updateOperation: (
    scenarioId: string,
    operationId: string,
    payload: ScenarioOperationPayload,
  ) =>
    apiPatch<ScenarioOperation>(
      `/api/v1/scenarios/${scenarioId}/operations/${operationId}`,
      payload,
    ),

  deleteOperation: (scenarioId: string, operationId: string) =>
    apiDelete<void>(
      `/api/v1/scenarios/${scenarioId}/operations/${operationId}`,
    ),

  calculate: (scenarioId: string) =>
    apiPost<ScenarioResults>(`/api/v1/scenarios/${scenarioId}/calculate`),

  getResults: (scenarioId: string) =>
    apiGet<ScenarioResults>(`/api/v1/scenarios/${scenarioId}/results`),

  getComparison: (scenarioId: string) =>
    apiGet<ScenarioComparison>(`/api/v1/scenarios/${scenarioId}/comparison`),

  listPriorityOverrides: (scenarioId: string) =>
    apiGet<ScenarioPriorityOverride[]>(
      `/api/v1/scenarios/${scenarioId}/priority-overrides`,
    ),

  setPriorityOverride: (scenarioId: string, data: ScenarioPriorityOverrideSetInput) =>
    apiPost<ScenarioPriorityOverride>(
      `/api/v1/scenarios/${scenarioId}/priority-overrides`,
      data,
    ),

  deletePriorityOverride: (scenarioId: string, overrideId: string) =>
    apiDelete<void>(
      `/api/v1/scenarios/${scenarioId}/priority-overrides/${overrideId}`,
    ),

  getPriorityComparison: (scenarioId: string, frameworkId: string) =>
    apiGet<ScenarioPriorityComparison>(
      `/api/v1/scenarios/${scenarioId}/priority-comparison`,
      { framework_id: frameworkId },
    ),
}

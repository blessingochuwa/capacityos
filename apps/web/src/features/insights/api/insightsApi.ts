import { apiGet } from '@/api/client'
import type { Page } from '@/types/entities'
import type { InsightsSummary, Signal } from '../types/insights'

/** Thin typed wrappers over apps/api's insights endpoints
 * (apps/api/app/api/v1/insights.py). Read-only, like features/capacity's
 * api module — no calculation happens here, these responses ARE the
 * backend's own classified signals. */

export interface DateRangeParams {
  start_date: string
  end_date: string
}

export interface TeamSummaryParams extends DateRangeParams {
  project_id?: string
  scenario_id?: string
}

export const insightsApi = {
  getPersonSignals: (personId: string, range: DateRangeParams) =>
    apiGet<Page<Signal>>(`/api/v1/insights/people/${personId}/signals`, {
      ...range,
    }),

  getTeamSignals: (teamId: string, range: DateRangeParams) =>
    apiGet<Page<Signal>>(`/api/v1/insights/teams/${teamId}/signals`, {
      ...range,
    }),

  getProjectSignals: (projectId: string, range: DateRangeParams) =>
    apiGet<Page<Signal>>(`/api/v1/insights/projects/${projectId}/signals`, {
      ...range,
    }),

  getScenarioSignals: (scenarioId: string) =>
    apiGet<Page<Signal>>(`/api/v1/insights/scenarios/${scenarioId}/signals`),

  getTeamSummary: (teamId: string, params: TeamSummaryParams) =>
    apiGet<InsightsSummary>(`/api/v1/insights/teams/${teamId}/summary`, {
      ...params,
    }),
}

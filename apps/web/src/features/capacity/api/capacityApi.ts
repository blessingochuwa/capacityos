import { apiGet } from '@/api/client'
import type {
  PersonCapacity,
  ProjectDemand,
  TeamCapacity,
} from '../types/capacity'

/** Thin typed wrappers over apps/api's three capacity endpoints
 * (apps/api/app/api/v1/capacity.py). No calculation happens here or
 * anywhere else in the frontend — these responses ARE the capacity
 * numbers, verbatim from the Phase 2 engine. */

export interface DateRangeParams {
  start_date: string
  end_date: string
}

export const capacityApi = {
  getPersonCapacity: (personId: string, range: DateRangeParams) =>
    apiGet<PersonCapacity>(`/api/v1/capacity/people/${personId}`, { ...range }),

  getTeamCapacity: (teamId: string, range: DateRangeParams) =>
    apiGet<TeamCapacity>(`/api/v1/capacity/teams/${teamId}`, { ...range }),

  getProjectDemand: (projectId: string, range: DateRangeParams) =>
    apiGet<ProjectDemand>(`/api/v1/capacity/projects/${projectId}`, {
      ...range,
    }),
}

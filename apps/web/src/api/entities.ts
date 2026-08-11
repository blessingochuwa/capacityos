import { apiGet } from './client'
import type {
  Allocation,
  AvailabilityException,
  Page,
  Person,
  Project,
  Team,
  TeamMembership,
} from '@/types/entities'

/** Read-only wrappers over apps/api's CRUD entity endpoints — Phase 3 is a
 * planning/viewing surface, so only the GET operations it needs are exposed
 * here. Reuses the existing Page<T> envelope and route shapes verbatim
 * (apps/api/app/api/v1/{people,teams,projects,allocations,availability_exceptions}.py). */

const LIST_ALL_LIMIT = 500

export const peopleApi = {
  list: () => apiGet<Page<Person>>('/api/v1/people', { limit: LIST_ALL_LIMIT }),
  get: (personId: string) => apiGet<Person>(`/api/v1/people/${personId}`),
}

export const teamsApi = {
  list: () => apiGet<Page<Team>>('/api/v1/teams', { limit: LIST_ALL_LIMIT }),
  get: (teamId: string) => apiGet<Team>(`/api/v1/teams/${teamId}`),
  listMembers: (teamId: string) =>
    apiGet<TeamMembership[]>(`/api/v1/teams/${teamId}/members`),
}

export const projectsApi = {
  list: () =>
    apiGet<Page<Project>>('/api/v1/projects', { limit: LIST_ALL_LIMIT }),
  get: (projectId: string) => apiGet<Project>(`/api/v1/projects/${projectId}`),
}

export const allocationsApi = {
  listForPerson: (personId: string) =>
    apiGet<Page<Allocation>>('/api/v1/allocations', {
      person_id: personId,
      limit: LIST_ALL_LIMIT,
    }),
}

export const availabilityExceptionsApi = {
  listForPerson: (personId: string) =>
    apiGet<Page<AvailabilityException>>('/api/v1/availability-exceptions', {
      person_id: personId,
      limit: LIST_ALL_LIMIT,
    }),
}

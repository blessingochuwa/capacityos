import type { Person, Project, Team } from '@/types/entities'
import type {
  PersonCapacity,
  ProjectDemand,
  TeamCapacity,
} from '@/features/capacity/types/capacity'

export function makePerson(overrides: Partial<Person> = {}): Person {
  return {
    id: 'person-1',
    first_name: 'Jane',
    last_name: 'Doe',
    display_name: 'Jane Doe',
    email: 'jane.doe@example.com',
    job_title: 'Product Designer',
    timezone: 'UTC',
    employment_status: 'active',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makeTeam(overrides: Partial<Team> = {}): Team {
  return {
    id: 'team-1',
    name: 'Product Design',
    description: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 'project-1',
    name: 'Website Redesign',
    description: null,
    status: 'active',
    start_date: null,
    end_date: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makePersonCapacity(
  overrides: Partial<PersonCapacity> = {},
): PersonCapacity {
  return {
    person_id: 'person-1',
    start_date: '2026-08-17',
    end_date: '2026-08-21',
    gross_capacity: '40.00',
    unavailable_hours: '0.00',
    effective_capacity: '40.00',
    allocated_hours: '32.00',
    remaining_capacity: '8.00',
    utilization: '0.8000',
    over_allocation: '0.00',
    daily_breakdown: [
      {
        date: '2026-08-17',
        scheduled_hours: '8.00',
        unavailable_hours: '0.00',
        effective_capacity: '8.00',
        allocated_hours: '6.00',
        remaining_capacity: '2.00',
        utilization: '0.7500',
        over_allocation: '0.00',
      },
    ],
    ...overrides,
  }
}

export function makeTeamCapacity(
  overrides: Partial<TeamCapacity> = {},
): TeamCapacity {
  return {
    team_id: 'team-1',
    start_date: '2026-08-17',
    end_date: '2026-08-21',
    gross_capacity: '80.00',
    unavailable_hours: '0.00',
    effective_capacity: '80.00',
    allocated_hours: '64.00',
    remaining_capacity: '16.00',
    utilization: '0.8000',
    over_allocation: '0.00',
    members: [],
    ...overrides,
  }
}

export function makeProjectDemand(
  overrides: Partial<ProjectDemand> = {},
): ProjectDemand {
  return {
    project_id: 'project-1',
    start_date: '2026-08-17',
    end_date: '2026-08-21',
    allocated_hours: '20.00',
    allocated_people: 1,
    daily_breakdown: [{ date: '2026-08-17', allocated_hours: '4.00' }],
    by_person: [{ person_id: 'person-1', allocated_hours: '20.00' }],
    ...overrides,
  }
}

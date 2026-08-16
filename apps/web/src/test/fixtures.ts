import type { Person, Project, Team } from '@/types/entities'
import type {
  PersonCapacity,
  ProjectDemand,
  TeamCapacity,
} from '@/features/capacity/types/capacity'
import type {
  AggregateCapacity,
  AggregateComparison,
  Impact,
  MetricDelta,
  PersonCapacityComparison,
  PersonCapacitySnapshot,
  Risk,
  Scenario,
  ScenarioComparison,
  ScenarioOperation,
  ScenarioOperationPayload,
} from '@/features/scenarios/types/scenario'
import type {
  InsightsSummary,
  Signal,
} from '@/features/insights/types/insights'

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

export function makeScenario(overrides: Partial<Scenario> = {}): Scenario {
  return {
    id: 'scenario-1',
    name: 'Launch earlier',
    description: null,
    status: 'draft',
    baseline_start_date: '2026-09-01',
    baseline_end_date: '2026-09-05',
    created_by: null,
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
    ...overrides,
  }
}

export function makeScenarioOperation(
  overrides: Partial<ScenarioOperation> & {
    payload?: ScenarioOperationPayload
  } = {},
): ScenarioOperation {
  return {
    id: 'operation-1',
    scenario_id: 'scenario-1',
    operation_type: 'add_allocation',
    sequence: 0,
    payload: {
      operation_type: 'add_allocation',
      person_id: 'person-1',
      project_id: 'project-1',
      hours: '20',
      start_date: '2026-09-01',
      end_date: '2026-09-05',
    },
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
    ...overrides,
  }
}

export function makeAggregateCapacity(
  overrides: Partial<AggregateCapacity> = {},
): AggregateCapacity {
  return {
    start_date: '2026-09-01',
    end_date: '2026-09-05',
    gross_capacity: '40.00',
    unavailable_hours: '0.00',
    effective_capacity: '40.00',
    allocated_hours: '20.00',
    remaining_capacity: '20.00',
    utilization: '0.5000',
    over_allocation: '0.00',
    ...overrides,
  }
}

export function makePersonCapacitySnapshot(
  overrides: Partial<PersonCapacitySnapshot> = {},
): PersonCapacitySnapshot {
  return {
    person_id: 'person-1',
    label: 'Jane Doe',
    is_hypothetical: false,
    start_date: '2026-09-01',
    end_date: '2026-09-05',
    gross_capacity: '40.00',
    unavailable_hours: '0.00',
    effective_capacity: '40.00',
    allocated_hours: '20.00',
    remaining_capacity: '20.00',
    utilization: '0.5000',
    over_allocation: '0.00',
    ...overrides,
  }
}

export function makeMetricDelta<T>(
  baseline: T,
  scenario: T,
  delta: T,
): MetricDelta<T> {
  return { baseline, scenario, delta }
}

export function makePersonCapacityComparison(
  overrides: Partial<PersonCapacityComparison> = {},
): PersonCapacityComparison {
  return {
    person_id: 'person-1',
    label: 'Jane Doe',
    is_hypothetical: false,
    baseline: makePersonCapacitySnapshot(),
    scenario: makePersonCapacitySnapshot({
      allocated_hours: '30.00',
      remaining_capacity: '10.00',
    }),
    utilization: makeMetricDelta<string | null>('0.5000', '0.7500', '0.2500'),
    remaining_capacity: makeMetricDelta('20.00', '10.00', '-10.00'),
    over_allocation: makeMetricDelta('0.00', '0.00', '0.00'),
    newly_over_allocated: false,
    ...overrides,
  }
}

export function makeRisk(overrides: Partial<Risk> = {}): Risk {
  return {
    type: 'over_allocation',
    person_id: 'person-1',
    label: 'Jane Doe',
    is_new: true,
    baseline_value: '0.00',
    scenario_value: '8.00',
    ...overrides,
  }
}

export function makeImpact(overrides: Partial<Impact> = {}): Impact {
  return {
    affected_people: ['person-1'],
    affected_projects: ['project-1'],
    affected_teams: [],
    affected_start_date: '2026-09-01',
    affected_end_date: '2026-09-05',
    ...overrides,
  }
}

export function makeAggregateComparison(
  overrides: Partial<AggregateComparison> = {},
): AggregateComparison {
  return {
    baseline: makeAggregateCapacity(),
    scenario: makeAggregateCapacity({
      allocated_hours: '30.00',
      remaining_capacity: '10.00',
      utilization: '0.7500',
    }),
    utilization: makeMetricDelta<string | null>('0.5000', '0.7500', '0.2500'),
    remaining_capacity: makeMetricDelta('20.00', '10.00', '-10.00'),
    over_allocation: makeMetricDelta('0.00', '0.00', '0.00'),
    over_allocated_people: makeMetricDelta(0, 0, 0),
    ...overrides,
  }
}

export function makeScenarioComparison(
  overrides: Partial<ScenarioComparison> = {},
): ScenarioComparison {
  return {
    scenario: makeScenario(),
    aggregate: makeAggregateComparison(),
    people: [makePersonCapacityComparison()],
    projects: [],
    risks: [],
    impact: makeImpact(),
    ...overrides,
  }
}

export function makeSignal(overrides: Partial<Signal> = {}): Signal {
  return {
    type: 'over_allocation',
    severity: 'critical',
    entity_type: 'person',
    entity_id: 'person-1',
    entity_label: 'Jane Doe',
    start_date: '2026-08-17',
    end_date: '2026-08-21',
    explanation:
      'Jane Doe is allocated 6.00h more than available capacity between Aug 17 and Aug 21.',
    effective_capacity: '40.00',
    allocated_hours: '46.00',
    remaining_capacity: '-6.00',
    excess_hours: '6.00',
    utilization: '1.1500',
    threshold_hours_per_day: null,
    concentration_ratio: null,
    concentration_person_ids: null,
    concentration_person_labels: null,
    min_utilization: null,
    min_utilization_person_id: null,
    min_utilization_person_label: null,
    max_utilization: null,
    max_utilization_person_id: null,
    max_utilization_person_label: null,
    affected_person_ids: ['person-1'],
    contributing_allocation_ids: [],
    scenario_id: null,
    is_new: null,
    trend: null,
    baseline_value: null,
    scenario_value: null,
    ...overrides,
  }
}

export function makeInsightsSummary(
  overrides: Partial<InsightsSummary> = {},
): InsightsSummary {
  return {
    team_id: 'team-1',
    team_label: 'Product Design',
    start_date: '2026-08-17',
    end_date: '2026-08-21',
    capacity: makeAggregateCapacity(),
    signal_counts: { critical: 0, warning: 0, info: 0 },
    utilization_distribution: [],
    concentration_areas: [],
    projects_under_pressure: [],
    scenario_id: null,
    scenario_delta: null,
    scenario_new_risk_count: 0,
    scenario_existing_risk_count: 0,
    ...overrides,
  }
}

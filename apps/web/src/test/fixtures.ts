import type { Person, Project, Team } from '@/types/entities'
import type { CurrentUser } from '@/features/auth/types/auth'
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
  ScenarioPriorityComparison,
  ScenarioPriorityOverride,
  ScenarioPriorityProjectComparison,
} from '@/features/scenarios/types/scenarioPriority'
import type {
  InsightsSummary,
  Signal,
} from '@/features/insights/types/insights'
import type {
  ImportApplyResult,
  ImportRowResult,
  ImportValidationReport,
} from '@/features/import-export/types/importExport'
import type {
  QualifiedPerson,
  Skill,
  SkillCoverage,
  TeamSkillCapacityEntry,
} from '@/features/skills/types/skills'
import type { Risk as RiskEntity } from '@/features/risks/types/risks'
import type {
  DependencyGraph,
  PortfolioRankingEntry,
  PortfolioSnapshot,
  PortfolioSnapshotComparison,
  PrioritizationCriterion,
  PrioritizationFramework,
  ProjectDependency,
  ProjectPriorityScore,
  SnapshotComparisonItem,
} from '@/features/prioritization/types/prioritization'
import type { Stakeholder } from '@/features/stakeholders/types/stakeholders'
import type {
  AIInsightResponse,
  AIResponseEnvelope,
} from '@/features/ai/types/ai'

export function makeCurrentUser(
  overrides: Partial<CurrentUser> = {},
): CurrentUser {
  return {
    id: 'user-1',
    email: 'owner@example.com',
    display_name: 'Owner Person',
    status: 'active',
    role: 'owner',
    active_organization: {
      id: 'org-1',
      name: 'Test Organization',
      slug: 'test-org',
      is_active: true,
    },
    organizations: [
      { id: 'org-1', name: 'Test Organization', slug: 'test-org', is_active: true },
    ],
    person_id: null,
    last_login_at: '2026-01-01T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    permissions: [
      'person.read',
      'person.write',
      'person.delete',
      'team.read',
      'team.write',
      'scenario.read',
      'scenario.write',
      'skill.read',
      'skill.write',
      'import.use',
      'export.use',
      'ai.use',
      'user.read',
      'user.write',
      'audit.read',
      'access.manage',
    ],
    accessible_team_ids: [],
    accessible_project_ids: [],
    ...overrides,
  }
}

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

export function makeScenarioPriorityOverride(
  overrides: Partial<ScenarioPriorityOverride> = {},
): ScenarioPriorityOverride {
  return {
    id: 'override-1',
    scenario_id: 'scenario-1',
    project_id: 'project-1',
    project_name: 'Website Redesign',
    framework_id: 'framework-1',
    framework_name: 'Feature RICE',
    framework_type: 'rice',
    values: { reach: '5000' },
    category: null,
    created_at: '2026-08-24T00:00:00Z',
    updated_at: '2026-08-24T00:00:00Z',
    ...overrides,
  }
}

export function makeScenarioPriorityProjectComparison(
  overrides: Partial<ScenarioPriorityProjectComparison> = {},
): ScenarioPriorityProjectComparison {
  return {
    project_id: 'project-1',
    project_name: 'Website Redesign',
    has_override: true,
    baseline_score: '400.00',
    baseline_rank: 2,
    baseline_category: null,
    baseline_missing_criteria: [],
    baseline_breakdown: { reach: '1000', impact: '2', confidence: '0.8', effort: '4' },
    scenario_score: '2000.00',
    scenario_rank: 1,
    scenario_category: null,
    scenario_missing_criteria: [],
    scenario_breakdown: { reach: '5000', impact: '2', confidence: '0.8', effort: '4' },
    changed: true,
    ...overrides,
  }
}

export function makeScenarioPriorityComparison(
  overrides: Partial<ScenarioPriorityComparison> = {},
): ScenarioPriorityComparison {
  return {
    scenario_id: 'scenario-1',
    framework_id: 'framework-1',
    framework_name: 'Feature RICE',
    framework_type: 'rice',
    has_changes: true,
    items: [makeScenarioPriorityProjectComparison()],
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
    skill_id: null,
    skill_label: null,
    skill_required_hours: null,
    skill_qualified_available_hours: null,
    skill_coverage_ratio: null,
    skill_gap_hours: null,
    skill_holder_ids: null,
    skill_holder_labels: null,
    skill_holder_ratio: null,
    risk_id: null,
    risk_description: null,
    risk_probability: null,
    risk_impact: null,
    risk_exposure: null,
    risk_status: null,
    risk_owner_person_id: null,
    risk_owner_label: null,
    risk_review_date: null,
    ...overrides,
  }
}

export function makeImportRowResult(
  overrides: Partial<ImportRowResult> = {},
): ImportRowResult {
  return {
    row_number: 1,
    status: 'valid_create',
    identity: 'email=jane.doe@example.com',
    matched_id: null,
    errors: [],
    ...overrides,
  }
}

export function makeImportValidationReport(
  overrides: Partial<ImportValidationReport> = {},
): ImportValidationReport {
  return {
    entity_type: 'person',
    mode: 'upsert',
    file_error: null,
    total_rows: 1,
    valid_create_count: 1,
    valid_update_count: 0,
    valid_unchanged_count: 0,
    invalid_count: 0,
    ready_to_apply: true,
    rows: [makeImportRowResult()],
    ...overrides,
  }
}

export function makeImportApplyResult(
  overrides: Partial<ImportApplyResult> = {},
): ImportApplyResult {
  return {
    entity_type: 'person',
    mode: 'upsert',
    file_error: null,
    applied: true,
    total_rows: 1,
    created_count: 1,
    updated_count: 0,
    unchanged_count: 0,
    invalid_count: 0,
    rows: [makeImportRowResult()],
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

export function makeSkill(overrides: Partial<Skill> = {}): Skill {
  return {
    id: 'skill-1',
    name: 'Backend Development',
    description: null,
    category: null,
    is_active: true,
    created_at: '2026-08-17T00:00:00Z',
    updated_at: '2026-08-17T00:00:00Z',
    person_count: 0,
    ...overrides,
  }
}

/** Named makeProjectRisk, not makeRisk, to avoid colliding with the
 * pre-existing scenario-domain makeRisk above (Risk from
 * features/scenarios/types/scenario — a capacity risk delta, a completely
 * different concept from this Phase 13 risk-register entity). */
export function makeProjectRisk(overrides: Partial<RiskEntity> = {}): RiskEntity {
  return {
    id: 'risk-1',
    project_id: 'project-1',
    description: 'Key vendor may miss the delivery deadline',
    cause: null,
    potential_effect: null,
    probability: 'medium',
    impact: 'medium',
    exposure: 'medium',
    response: null,
    owner_person_id: null,
    status: 'open',
    review_date: null,
    created_at: '2026-08-17T00:00:00Z',
    updated_at: '2026-08-17T00:00:00Z',
    ...overrides,
  }
}

export function makeStakeholder(overrides: Partial<Stakeholder> = {}): Stakeholder {
  return {
    id: 'stakeholder-1',
    project_id: 'project-1',
    name: 'Jordan Client',
    person_id: null,
    role: 'Sponsor',
    influence: 'medium',
    interest: 'medium',
    decision_authority: 'informed',
    communication_needs: null,
    created_at: '2026-08-17T00:00:00Z',
    updated_at: '2026-08-17T00:00:00Z',
    ...overrides,
  }
}

export function makeQualifiedPerson(
  overrides: Partial<QualifiedPerson> = {},
): QualifiedPerson {
  return {
    person_id: 'person-1',
    person_label: 'Jane Doe',
    proficiency: 'proficient',
    qualified_available_hours: '20.00',
    ...overrides,
  }
}

export function makeSkillCoverage(
  overrides: Partial<SkillCoverage> = {},
): SkillCoverage {
  return {
    requirement_id: 'requirement-1',
    skill_id: 'skill-1',
    skill_label: 'Backend Development',
    required_hours: '80.00',
    minimum_proficiency: null,
    qualified_available_hours: '80.00',
    coverage_ratio: '1.0000',
    gap_hours: '0.00',
    qualified_people: [makeQualifiedPerson()],
    ...overrides,
  }
}

export function makeAIInsightResponse(
  overrides: Partial<AIInsightResponse> = {},
): AIInsightResponse {
  return {
    summary: 'No material capacity risk is currently detected for this scope.',
    key_findings: [],
    risks: [],
    recommendations: [],
    confidence: 'high',
    generated_at: '2026-08-17T12:00:00Z',
    provider: 'mock',
    model: 'claude-sonnet-5',
    ...overrides,
  }
}

export function makeAIResponseEnvelope(
  overrides: Partial<AIResponseEnvelope> = {},
): AIResponseEnvelope {
  return {
    status: 'ok',
    response: makeAIInsightResponse(),
    message: null,
    ...overrides,
  }
}

export function makeTeamSkillCapacityEntry(
  overrides: Partial<TeamSkillCapacityEntry> = {},
): TeamSkillCapacityEntry {
  return {
    skill_id: 'skill-1',
    skill_label: 'Backend Development',
    qualified_available_hours: '20.00',
    qualified_people: [makeQualifiedPerson()],
    ...overrides,
  }
}

export function makePrioritizationCriterion(
  overrides: Partial<PrioritizationCriterion> = {},
): PrioritizationCriterion {
  return {
    id: 'criterion-1',
    key: 'reach',
    name: 'Reach',
    weight: null,
    is_editable: false,
    sequence: 0,
    ...overrides,
  }
}

export function makePrioritizationFramework(
  overrides: Partial<PrioritizationFramework> = {},
): PrioritizationFramework {
  return {
    id: 'framework-1',
    organization_id: 'org-1',
    name: 'Feature RICE',
    framework_type: 'rice',
    is_active: true,
    criteria: [
      makePrioritizationCriterion({ id: 'c-reach', key: 'reach', name: 'Reach' }),
      makePrioritizationCriterion({ id: 'c-impact', key: 'impact', name: 'Impact' }),
      makePrioritizationCriterion({ id: 'c-confidence', key: 'confidence', name: 'Confidence' }),
      makePrioritizationCriterion({ id: 'c-effort', key: 'effort', name: 'Effort' }),
    ],
    created_at: '2026-08-24T00:00:00Z',
    updated_at: '2026-08-24T00:00:00Z',
    ...overrides,
  }
}

export function makeProjectPriorityScore(
  overrides: Partial<ProjectPriorityScore> = {},
): ProjectPriorityScore {
  return {
    id: 'score-1',
    project_id: 'project-1',
    framework_id: 'framework-1',
    framework_name: 'Feature RICE',
    framework_type: 'rice',
    score: '400.00',
    missing_criteria: [],
    breakdown: { reach: '1000', impact: '2', confidence: '0.8', effort: '4' },
    category: null,
    notes: null,
    created_at: '2026-08-24T00:00:00Z',
    updated_at: '2026-08-24T00:00:00Z',
    ...overrides,
  }
}

export function makePortfolioRankingEntry(
  overrides: Partial<PortfolioRankingEntry> = {},
): PortfolioRankingEntry {
  return {
    project_id: 'project-1',
    project_name: 'Website Redesign',
    score: '400.00',
    rank: 1,
    missing_criteria: [],
    breakdown: { reach: '1000', impact: '2', confidence: '0.8', effort: '4' },
    category: null,
    ...overrides,
  }
}

export function makePortfolioSnapshot(
  overrides: Partial<PortfolioSnapshot> = {},
): PortfolioSnapshot {
  return {
    id: 'snapshot-1',
    framework_id: 'framework-1',
    framework_name: 'Feature RICE',
    framework_type: 'rice',
    taken_at: '2026-08-25T00:00:00Z',
    entries: [makePortfolioRankingEntry()],
    ...overrides,
  }
}

export function makeProjectDependency(
  overrides: Partial<ProjectDependency> = {},
): ProjectDependency {
  return {
    id: 'dependency-1',
    from_project_id: 'project-1',
    from_project_name: 'Website Redesign',
    to_project_id: 'project-2',
    to_project_name: 'Mobile App',
    dependency_type: 'blocks',
    created_at: '2026-08-24T00:00:00Z',
    ...overrides,
  }
}

export function makeSnapshotComparisonItem(
  overrides: Partial<SnapshotComparisonItem> = {},
): SnapshotComparisonItem {
  return {
    project_id: 'project-1',
    project_name: 'Website Redesign',
    status: 'unchanged',
    rank_from: 1,
    rank_to: 1,
    score_from: '400.00',
    score_to: '400.00',
    category_from: null,
    category_to: null,
    ...overrides,
  }
}

export function makePortfolioSnapshotComparison(
  overrides: Partial<PortfolioSnapshotComparison> = {},
): PortfolioSnapshotComparison {
  return {
    from_snapshot_id: 'snapshot-1',
    to_snapshot_id: 'snapshot-2',
    framework_id: 'framework-1',
    framework_name: 'Feature RICE',
    framework_type: 'rice',
    items: [makeSnapshotComparisonItem()],
    ...overrides,
  }
}

export function makeDependencyGraph(overrides: Partial<DependencyGraph> = {}): DependencyGraph {
  return {
    nodes: [
      { project_id: 'project-1', project_name: 'Website Redesign' },
      { project_id: 'project-2', project_name: 'Mobile App' },
    ],
    edges: [makeProjectDependency()],
    ...overrides,
  }
}

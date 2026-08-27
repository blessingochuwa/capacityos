"""Builds typed, intentional AI context objects from the EXISTING
deterministic services (CapacityService, InsightService,
ScenarioCalculationService, SkillCapacityService) — Phase 8 never
recalculates a capacity/signal/coverage number itself (CLAUDE.md §21/§35).

No SQLAlchemy model is ever serialized into a prompt; only these explicit,
minimal dataclasses are (see app/integrations/ai/base.py's
AIGenerationRequest.context and docs/adr/0008-phase-8-ai-insight-layer.md
"Data minimization"). Entity labels are display names, never emails or
other contact information — data minimization, not just structure.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.core.exceptions import NotFoundError
from app.domain.capacity import PersonCapacityResult, TeamCapacityResult
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.team import TeamRepository
from app.schemas.insights import SignalRead
from app.services.capacity import CapacityService
from app.services.insight_service import InsightService
from app.services.portfolio_snapshot import PortfolioSnapshotService
from app.services.project_priority_score import ProjectPriorityScoreService
from app.services.scenario_calculation import ScenarioCalculationService
from app.services.scenario_priority import ScenarioPriorityService
from app.services.skill_capacity import SkillCapacityService


@dataclass(frozen=True)
class AIEntityContext:
    entity_type: str
    entity_id: uuid.UUID
    entity_label: str


@dataclass(frozen=True)
class AICapacityFact:
    effective_capacity: Decimal
    allocated_hours: Decimal
    remaining_capacity: Decimal
    utilization: Decimal | None
    over_allocation: Decimal


@dataclass(frozen=True)
class AISignalFact:
    type: str
    severity: str
    entity_type: str
    entity_id: uuid.UUID
    entity_label: str
    explanation: str
    """A complete, already-composed sentence from InsightService's own
    explanation builders — never raw user-entered text."""


@dataclass(frozen=True)
class AISkillCoverageFact:
    skill_id: uuid.UUID
    skill_label: str
    qualified_available_hours: Decimal
    required_hours: Decimal | None = None
    gap_hours: Decimal | None = None
    coverage_ratio: Decimal | None = None
    """required_hours/gap_hours/coverage_ratio are None for team-scope
    facts — a team has no stored skill demand of its own, only a project
    does (see docs/adr/0007-phase-7-skills-bottleneck-analysis.md)."""


@dataclass(frozen=True)
class AIScenarioFact:
    scenario_id: uuid.UUID
    scenario_label: str
    baseline_remaining_capacity: Decimal
    scenario_remaining_capacity: Decimal
    baseline_over_allocation: Decimal
    scenario_over_allocation: Decimal
    new_risk_count: int
    existing_risk_count: int
    new_risk_descriptions: tuple[str, ...]


@dataclass(frozen=True)
class AIPriorityFact:
    """Phase 19 — the same (score, PriorityScoreResult) shape
    ProjectPriorityScoreService.get already returns and
    project_priority_score_to_read already renders to the API, just
    reshaped into this module's DB-free fact vocabulary. No number here
    is ever recomputed by this module — score/missing_criteria/breakdown/
    category are copied verbatim from the result the deterministic
    prioritization engine (app/domain/prioritization.py) already
    produced."""

    score_id: uuid.UUID
    project_label: str
    framework_id: uuid.UUID
    framework_name: str
    framework_type: str
    score: Decimal | None
    missing_criteria: tuple[str, ...]
    breakdown: dict[str, Decimal]
    category: str | None


@dataclass(frozen=True)
class AISnapshotComparisonItemFact:
    """One project's row in the Phase 22 comparison — every field is
    copied verbatim from SnapshotComparisonItem
    (app/domain/portfolio_snapshot.py), never recomputed here."""

    project_id: uuid.UUID
    project_name: str
    status: str
    rank_from: int | None
    rank_to: int | None
    score_from: Decimal | None
    score_to: Decimal | None
    category_from: str | None
    category_to: str | None


@dataclass(frozen=True)
class AISnapshotComparisonFact:
    """Phase 23 — the same (from_snapshot, to_snapshot, items) triple
    PortfolioSnapshotService.compare already returns and
    portfolio_snapshot_comparison_to_read already renders to the API,
    reshaped into this module's DB-free fact vocabulary. No status, rank,
    score, or category is ever recomputed by this module — this is a
    comparison of two already-frozen Phase 21 snapshots (Phase 22), and
    this fact only copies that already-computed diff."""

    from_snapshot_id: uuid.UUID
    to_snapshot_id: uuid.UUID
    from_taken_at: datetime
    to_taken_at: datetime
    framework_name: str
    framework_type: str
    items: tuple[AISnapshotComparisonItemFact, ...]


@dataclass(frozen=True)
class AIScenarioPriorityComparisonItemFact:
    """One project's row in the Phase 20 comparison — every field is
    copied verbatim from ScenarioPriorityComparisonItem
    (app/services/scenario_priority.py), never recomputed here."""

    project_id: uuid.UUID
    project_name: str
    has_override: bool
    baseline_score: Decimal | None
    baseline_rank: int | None
    baseline_category: str | None
    scenario_score: Decimal | None
    scenario_rank: int | None
    scenario_category: str | None
    changed: bool


@dataclass(frozen=True)
class AIScenarioPriorityComparisonFact:
    """Phase 26 — the same (scenario, framework, items) triple
    ScenarioPriorityService.compare already returns and
    scenario_priority_comparison_to_read (app/api/v1/scenarios.py) already
    renders to the API, reshaped into this module's DB-free fact
    vocabulary. No score, rank, or category is ever recomputed by this
    module — a comparison item's baseline/scenario results are already
    computed once by the Phase 17/18 deterministic engine before this
    module ever sees them."""

    scenario_id: uuid.UUID
    scenario_label: str
    framework_name: str
    framework_type: str
    has_changes: bool
    items: tuple[AIScenarioPriorityComparisonItemFact, ...]


@dataclass(frozen=True)
class AIInsightContext:
    scope: AIEntityContext
    start_date: date | None
    end_date: date | None
    capacity: AICapacityFact | None
    signals: tuple[AISignalFact, ...]
    skill_coverage: tuple[AISkillCoverageFact, ...]
    scenario: AIScenarioFact | None
    priority: AIPriorityFact | None = None
    snapshot_comparison: AISnapshotComparisonFact | None = None
    scenario_priority_comparison: AIScenarioPriorityComparisonFact | None = None

    def known_references(self) -> frozenset[tuple[str, str]]:
        """(reference_type, id-as-str) pairs actually present in this
        context — the allow-list AIService checks every model-returned
        source_reference against before it reaches the client (see
        docs/adr/0008-phase-8-ai-insight-layer.md, "Grounding enforcement")."""
        refs: set[tuple[str, str]] = {("capacity", str(self.scope.entity_id))}
        for signal in self.signals:
            refs.add(("signal", str(signal.entity_id)))
        for coverage in self.skill_coverage:
            refs.add(("skill_coverage", str(coverage.skill_id)))
        if self.scenario is not None:
            refs.add(("scenario", str(self.scenario.scenario_id)))
        if self.priority is not None:
            refs.add(("priority_score", str(self.priority.score_id)))
        if self.snapshot_comparison is not None:
            for item in self.snapshot_comparison.items:
                refs.add(("snapshot_comparison", str(item.project_id)))
        if self.scenario_priority_comparison is not None:
            for item in self.scenario_priority_comparison.items:
                refs.add(("scenario_priority_comparison", str(item.project_id)))
        return frozenset(refs)


def _capacity_fact(result: PersonCapacityResult | TeamCapacityResult) -> AICapacityFact:
    return AICapacityFact(
        effective_capacity=result.effective_capacity,
        allocated_hours=result.allocated_hours,
        remaining_capacity=result.remaining_capacity,
        utilization=result.utilization,
        over_allocation=result.over_allocation,
    )


def _signal_fact(signal: SignalRead) -> AISignalFact:
    return AISignalFact(
        type=signal.type,
        severity=signal.severity,
        entity_type=signal.entity_type,
        entity_id=signal.entity_id,
        entity_label=signal.entity_label,
        explanation=signal.explanation,
    )


class AIContextBuilder:
    """One place service results become AI context — mirrors how
    app/services/planning_facts.py is the one place ORM rows become
    capacity facts."""

    def __init__(
        self,
        capacity_service: CapacityService,
        insight_service: InsightService,
        scenario_calculation_service: ScenarioCalculationService,
        skill_capacity_service: SkillCapacityService,
        priority_score_service: ProjectPriorityScoreService,
        portfolio_snapshot_service: PortfolioSnapshotService,
        scenario_priority_service: ScenarioPriorityService,
        person_repository: PersonRepository,
        team_repository: TeamRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self.capacity_service = capacity_service
        self.insight_service = insight_service
        self.scenario_calculation_service = scenario_calculation_service
        self.skill_capacity_service = skill_capacity_service
        self.priority_score_service = priority_score_service
        self.portfolio_snapshot_service = portfolio_snapshot_service
        self.scenario_priority_service = scenario_priority_service
        self.person_repository = person_repository
        self.team_repository = team_repository
        self.project_repository = project_repository

    def build_for_scope(
        self,
        organization_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        start_date: date,
        end_date: date,
        *,
        signal_type_filter: str | None = None,
    ) -> AIInsightContext:
        if entity_type == "person":
            result = self.capacity_service.get_person_capacity(
                organization_id, entity_id, start_date, end_date
            )
            capacity = _capacity_fact(result)
            label = self._person_label(organization_id, entity_id)
            signals = self.insight_service.get_person_signals(
                organization_id, entity_id, start_date, end_date
            )
            skill_coverage: tuple[AISkillCoverageFact, ...] = ()
        elif entity_type == "team":
            team_result, _ = self.capacity_service.get_team_capacity(
                organization_id, entity_id, start_date, end_date
            )
            capacity = _capacity_fact(team_result)
            label = self._team_label(organization_id, entity_id)
            signals = self.insight_service.get_team_signals(
                organization_id, entity_id, start_date, end_date
            )
            skill_coverage = self._team_skill_coverage(
                organization_id, entity_id, start_date, end_date
            )
        elif entity_type == "project":
            # ProjectDemandResult has no capacity concept (demand only) —
            # never fabricate an AICapacityFact for a project scope.
            capacity = None
            label = self._project_label(organization_id, entity_id)
            signals = self.insight_service.get_project_signals(
                organization_id, entity_id, start_date, end_date
            )
            skill_coverage = self._project_skill_coverage(
                organization_id, entity_id, start_date, end_date
            )
        else:
            raise NotFoundError("scope", entity_type)

        if signal_type_filter is not None:
            signals = [s for s in signals if s.type == signal_type_filter]

        return AIInsightContext(
            scope=AIEntityContext(entity_type, entity_id, label),
            start_date=start_date,
            end_date=end_date,
            capacity=capacity,
            signals=tuple(_signal_fact(s) for s in signals),
            skill_coverage=skill_coverage,
            scenario=None,
        )

    def build_for_scenario(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID
    ) -> AIInsightContext:
        comparison = self.scenario_calculation_service.comparison(organization_id, scenario_id)
        scenario = comparison.scenario
        aggregate = comparison.aggregate
        signals = self.insight_service.get_scenario_signals(organization_id, scenario_id)
        scenario_fact = AIScenarioFact(
            scenario_id=scenario.id,
            scenario_label=scenario.name,
            baseline_remaining_capacity=aggregate.remaining_capacity.baseline,
            scenario_remaining_capacity=aggregate.remaining_capacity.scenario,
            baseline_over_allocation=aggregate.over_allocation.baseline,
            scenario_over_allocation=aggregate.over_allocation.scenario,
            new_risk_count=sum(1 for r in comparison.risks if r.is_new),
            existing_risk_count=sum(1 for r in comparison.risks if not r.is_new),
            new_risk_descriptions=tuple(
                f"{r.label}: {r.type} (baseline {r.baseline_value}, scenario {r.scenario_value})"
                for r in comparison.risks
                if r.is_new
            ),
        )
        return AIInsightContext(
            scope=AIEntityContext("scenario", scenario.id, scenario.name),
            start_date=scenario.baseline_start_date,
            end_date=scenario.baseline_end_date,
            capacity=None,
            signals=tuple(_signal_fact(s) for s in signals),
            skill_coverage=(),
            scenario=scenario_fact,
        )

    def build_for_priority_score(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, score_id: uuid.UUID
    ) -> AIInsightContext:
        """Phase 19. Reuses ProjectPriorityScoreService.get verbatim — the
        exact same (score, PriorityScoreResult) pair
        project_priority_score_to_read already builds the API response
        from — rather than recomputing anything itself, matching every
        other build_for_* method's "call the existing deterministic
        service, never recalculate" discipline."""
        score, result = self.priority_score_service.get(organization_id, project_id, score_id)
        label = self._project_label(organization_id, project_id)
        priority_fact = AIPriorityFact(
            score_id=score.id,
            project_label=label,
            framework_id=score.framework_id,
            framework_name=score.framework.name,
            framework_type=score.framework.framework_type.value,
            score=result.score,
            missing_criteria=result.missing_criteria,
            breakdown=result.breakdown,
            category=result.category.value if result.category is not None else None,
        )
        return AIInsightContext(
            scope=AIEntityContext("project", project_id, label),
            start_date=None,
            end_date=None,
            capacity=None,
            signals=(),
            skill_coverage=(),
            scenario=None,
            priority=priority_fact,
        )

    def build_for_snapshot_comparison(
        self,
        organization_id: uuid.UUID,
        from_snapshot_id: uuid.UUID,
        to_snapshot_id: uuid.UUID,
    ) -> AIInsightContext:
        """Phase 23. Reuses PortfolioSnapshotService.compare verbatim — the
        exact same (from_snapshot, to_snapshot, items) triple
        portfolio_snapshot_comparison_to_read already builds the API
        response from — rather than recomputing anything itself, matching
        build_for_priority_score's own "call the existing deterministic
        service, never recalculate" discipline. Framework-mismatch (422)
        and an unknown or cross-organization snapshot id (404) propagate
        from PortfolioSnapshotService.compare unchanged."""
        from_snapshot, to_snapshot, items = self.portfolio_snapshot_service.compare(
            organization_id, from_snapshot_id, to_snapshot_id
        )
        comparison_fact = AISnapshotComparisonFact(
            from_snapshot_id=from_snapshot.id,
            to_snapshot_id=to_snapshot.id,
            from_taken_at=from_snapshot.created_at,
            to_taken_at=to_snapshot.created_at,
            framework_name=to_snapshot.framework_name,
            framework_type=to_snapshot.framework_type.value,
            items=tuple(
                AISnapshotComparisonItemFact(
                    project_id=uuid.UUID(item.project_id),
                    project_name=item.project_name,
                    status=item.status.value,
                    rank_from=item.rank_from,
                    rank_to=item.rank_to,
                    score_from=item.score_from,
                    score_to=item.score_to,
                    category_from=(
                        item.category_from.value if item.category_from is not None else None
                    ),
                    category_to=item.category_to.value if item.category_to is not None else None,
                )
                for item in items
            ),
        )
        label = f"{to_snapshot.framework_name} snapshot comparison"
        return AIInsightContext(
            scope=AIEntityContext("portfolio_snapshot_comparison", to_snapshot.id, label),
            start_date=None,
            end_date=None,
            capacity=None,
            signals=(),
            skill_coverage=(),
            scenario=None,
            snapshot_comparison=comparison_fact,
        )

    def build_for_scenario_priority_comparison(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID, framework_id: uuid.UUID
    ) -> AIInsightContext:
        """Phase 26. Reuses ScenarioPriorityService.compare verbatim — the
        exact same (scenario, framework, items) triple
        scenario_priority_comparison_to_read already builds the API
        response from — rather than recomputing anything itself, matching
        build_for_snapshot_comparison's own "call the existing
        deterministic service, never recalculate" discipline. An unknown
        or cross-organization scenario/framework id (404) propagates from
        ScenarioPriorityService.compare unchanged."""
        scenario, framework, items = self.scenario_priority_service.compare(
            organization_id, scenario_id, framework_id
        )
        comparison_fact = AIScenarioPriorityComparisonFact(
            scenario_id=scenario.id,
            scenario_label=scenario.name,
            framework_name=framework.name,
            framework_type=framework.framework_type.value,
            has_changes=any(item.changed for item in items),
            items=tuple(
                AIScenarioPriorityComparisonItemFact(
                    project_id=item.project.id,
                    project_name=item.project.name,
                    has_override=item.has_override,
                    baseline_score=item.baseline_result.score,
                    baseline_rank=item.baseline_rank,
                    baseline_category=(
                        item.baseline_result.category.value
                        if item.baseline_result.category is not None
                        else None
                    ),
                    scenario_score=item.scenario_result.score,
                    scenario_rank=item.scenario_rank,
                    scenario_category=(
                        item.scenario_result.category.value
                        if item.scenario_result.category is not None
                        else None
                    ),
                    changed=item.changed,
                )
                for item in items
            ),
        )
        return AIInsightContext(
            scope=AIEntityContext("scenario_priority_comparison", scenario.id, scenario.name),
            start_date=None,
            end_date=None,
            capacity=None,
            signals=(),
            skill_coverage=(),
            scenario=None,
            scenario_priority_comparison=comparison_fact,
        )

    def _team_skill_coverage(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, start_date: date, end_date: date
    ) -> tuple[AISkillCoverageFact, ...]:
        capacity = self.skill_capacity_service.get_team_skill_capacity(
            organization_id, team_id, start_date, end_date
        )
        return tuple(
            AISkillCoverageFact(
                skill_id=entry.skill_id,
                skill_label=entry.skill_label,
                qualified_available_hours=entry.qualified_available_hours,
            )
            for entry in capacity.skills
        )

    def _project_skill_coverage(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, start_date: date, end_date: date
    ) -> tuple[AISkillCoverageFact, ...]:
        coverage = self.skill_capacity_service.get_project_skill_coverage(
            organization_id, project_id, start_date, end_date
        )
        return tuple(
            AISkillCoverageFact(
                skill_id=requirement.skill_id,
                skill_label=requirement.skill_label,
                qualified_available_hours=requirement.qualified_available_hours,
                required_hours=requirement.required_hours,
                gap_hours=requirement.gap_hours,
                coverage_ratio=requirement.coverage_ratio,
            )
            for requirement in coverage.requirements
        )

    def _person_label(self, organization_id: uuid.UUID, person_id: uuid.UUID) -> str:
        person = self.person_repository.get(person_id, organization_id)
        if person is None:
            raise NotFoundError("Person", person_id)
        return person.display_name

    def _team_label(self, organization_id: uuid.UUID, team_id: uuid.UUID) -> str:
        team = self.team_repository.get(team_id, organization_id)
        if team is None:
            raise NotFoundError("Team", team_id)
        return team.name

    def _project_label(self, organization_id: uuid.UUID, project_id: uuid.UUID) -> str:
        project = self.project_repository.get(project_id, organization_id)
        if project is None:
            raise NotFoundError("Project", project_id)
        return project.name

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
from datetime import date
from decimal import Decimal

from app.core.exceptions import NotFoundError
from app.domain.capacity import PersonCapacityResult, TeamCapacityResult
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.team import TeamRepository
from app.schemas.insights import SignalRead
from app.services.capacity import CapacityService
from app.services.insight_service import InsightService
from app.services.scenario_calculation import ScenarioCalculationService
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
class AIInsightContext:
    scope: AIEntityContext
    start_date: date | None
    end_date: date | None
    capacity: AICapacityFact | None
    signals: tuple[AISignalFact, ...]
    skill_coverage: tuple[AISkillCoverageFact, ...]
    scenario: AIScenarioFact | None

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
        person_repository: PersonRepository,
        team_repository: TeamRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self.capacity_service = capacity_service
        self.insight_service = insight_service
        self.scenario_calculation_service = scenario_calculation_service
        self.skill_capacity_service = skill_capacity_service
        self.person_repository = person_repository
        self.team_repository = team_repository
        self.project_repository = project_repository

    def build_for_scope(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        start_date: date,
        end_date: date,
        *,
        signal_type_filter: str | None = None,
    ) -> AIInsightContext:
        if entity_type == "person":
            result = self.capacity_service.get_person_capacity(entity_id, start_date, end_date)
            capacity = _capacity_fact(result)
            label = self._person_label(entity_id)
            signals = self.insight_service.get_person_signals(entity_id, start_date, end_date)
            skill_coverage: tuple[AISkillCoverageFact, ...] = ()
        elif entity_type == "team":
            team_result, _ = self.capacity_service.get_team_capacity(
                entity_id, start_date, end_date
            )
            capacity = _capacity_fact(team_result)
            label = self._team_label(entity_id)
            signals = self.insight_service.get_team_signals(entity_id, start_date, end_date)
            skill_coverage = self._team_skill_coverage(entity_id, start_date, end_date)
        elif entity_type == "project":
            # ProjectDemandResult has no capacity concept (demand only) —
            # never fabricate an AICapacityFact for a project scope.
            capacity = None
            label = self._project_label(entity_id)
            signals = self.insight_service.get_project_signals(entity_id, start_date, end_date)
            skill_coverage = self._project_skill_coverage(entity_id, start_date, end_date)
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

    def build_for_scenario(self, scenario_id: uuid.UUID) -> AIInsightContext:
        comparison = self.scenario_calculation_service.comparison(scenario_id)
        scenario = comparison.scenario
        aggregate = comparison.aggregate
        signals = self.insight_service.get_scenario_signals(scenario_id)
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

    def _team_skill_coverage(
        self, team_id: uuid.UUID, start_date: date, end_date: date
    ) -> tuple[AISkillCoverageFact, ...]:
        capacity = self.skill_capacity_service.get_team_skill_capacity(
            team_id, start_date, end_date
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
        self, project_id: uuid.UUID, start_date: date, end_date: date
    ) -> tuple[AISkillCoverageFact, ...]:
        coverage = self.skill_capacity_service.get_project_skill_coverage(
            project_id, start_date, end_date
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

    def _person_label(self, person_id: uuid.UUID) -> str:
        person = self.person_repository.get(person_id)
        if person is None:
            raise NotFoundError("Person", person_id)
        return person.display_name

    def _team_label(self, team_id: uuid.UUID) -> str:
        team = self.team_repository.get(team_id)
        if team is None:
            raise NotFoundError("Team", team_id)
        return team.name

    def _project_label(self, project_id: uuid.UUID) -> str:
        project = self.project_repository.get(project_id)
        if project is None:
            raise NotFoundError("Project", project_id)
        return project.name

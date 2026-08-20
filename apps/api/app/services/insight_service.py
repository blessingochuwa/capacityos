"""Orchestrates operational-insight signals on top of the existing
CapacityService and ScenarioCalculationService (CLAUDE.md §39 Phase 5).

No second capacity engine: every classification here consumes numbers
already produced by app/domain/capacity.py (via CapacityService) or
app/domain/scenario.py (via ScenarioCalculationService), plus the pure
classification helpers in app/domain/insights.py. Scenario signals wrap,
never duplicate, ScenarioCalculationService's own risk detection. See
docs/adr/0005-phase-5-operational-insights.md.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.domain.capacity import (
    PersonCapacityResult,
    ProjectDemandResult,
    TeamCapacityResult,
    aggregate_team_capacity,
    calculate_period_capacity,
)
from app.domain.insights import (
    CapacitySignalType,
    ConcentrationResult,
    ImbalanceResult,
    ScenarioSignalTrend,
    calculate_concentration,
    calculate_imbalance,
    capacity_signal_severity,
    classify_capacity_signal,
    scenario_risk_severity,
    scenario_risk_trend,
)
from app.domain.skills import (
    QualifiedPerson,
    SkillConcentrationResult,
    SkillCoverageResult,
    calculate_skill_concentration,
    calculate_skill_coverage,
    is_qualified,
)
from app.models.person_skill import PersonSkill
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_skill_requirement import ProjectSkillRequirementRepository
from app.repositories.skill import SkillRepository
from app.repositories.team import TeamRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.insights import (
    ConcentrationAreaRead,
    EntityType,
    InsightsSummaryRead,
    ProjectPressureRead,
    Severity,
    SeverityCounts,
    SignalRead,
    SignalType,
    UtilizationPoint,
)
from app.schemas.scenario import (
    AggregateCapacityRead,
    AggregateComparisonRead,
    RiskRead,
    ScenarioRead,
)
from app.services.capacity import CapacityService
from app.services.planning_facts import load_people_facts
from app.services.scenario_calculation import ScenarioCalculationService

ZERO = Decimal("0.00")

_SEVERITY_RANK: dict[Severity, int] = {"critical": 0, "warning": 1, "info": 2}
_TYPE_RANK: dict[SignalType, int] = {
    "over_allocation": 0,
    "scenario_new_risk": 1,
    "scenario_existing_risk": 1,
    "low_capacity": 2,
    "project_capacity_pressure": 2,
    "skill_gap": 2,
    "single_skill_holder": 2,
    "zero_remaining_capacity": 3,
    "capacity_imbalance": 4,
    "concentration_risk": 5,
    "skill_concentration": 5,
}
"""The deterministic sort key used by _prioritize. Severity dominates (tier
1) because it is the one objective "how bad" fact every signal category
shares; is_new/type/label/id are tiebreakers within a severity tier only.
This deliberately refines the brief's flat example ordering, which would
let a merely-informational new scenario signal outrank an existing critical
over-allocation — see docs/adr/0005-phase-5-operational-insights.md."""


class InsightService:
    """Classifies existing capacity/scenario facts into explainable,
    prioritized signals. Holds no capacity or risk-detection formula of its
    own — see app/domain/insights.py (pure classification) and
    CapacityService/ScenarioCalculationService (the facts themselves)."""

    def __init__(
        self,
        schedule_repository: WorkingScheduleRepository,
        availability_repository: AvailabilityExceptionRepository,
        allocation_repository: AllocationRepository,
        person_repository: PersonRepository,
        team_repository: TeamRepository,
        project_repository: ProjectRepository,
        capacity_service: CapacityService,
        scenario_calculation_service: ScenarioCalculationService,
        low_capacity_threshold_hours_per_day: Decimal,
        person_skill_repository: PersonSkillRepository,
        skill_repository: SkillRepository,
        project_skill_requirement_repository: ProjectSkillRequirementRepository,
    ) -> None:
        self.schedule_repository = schedule_repository
        self.availability_repository = availability_repository
        self.allocation_repository = allocation_repository
        self.person_repository = person_repository
        self.team_repository = team_repository
        self.project_repository = project_repository
        self.capacity_service = capacity_service
        self.scenario_calculation_service = scenario_calculation_service
        self.low_capacity_threshold_hours_per_day = low_capacity_threshold_hours_per_day
        self.person_skill_repository = person_skill_repository
        self.skill_repository = skill_repository
        self.project_skill_requirement_repository = project_skill_requirement_repository

    # -- Public entry points ------------------------------------------------

    def get_person_signals(
        self, organization_id: uuid.UUID, person_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[SignalRead]:
        result = self.capacity_service.get_person_capacity(
            organization_id, person_id, start_date, end_date
        )
        label = self._person_labels(organization_id, [person_id]).get(person_id, "Unknown")
        signal = self._capacity_signal("person", person_id, label, result, start_date, end_date)
        return self._prioritize([signal] if signal is not None else [])

    def get_team_signals(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[SignalRead]:
        """A/B/C at team-aggregate scope AND per-member scope (an
        individual's over-allocation/zero/low-capacity is never hidden
        behind a healthy team total — same principle
        aggregate_team_capacity's own docstring states), plus E
        (capacity_imbalance) once for the team."""
        team_result, members = self.capacity_service.get_team_capacity(
            organization_id, team_id, start_date, end_date
        )
        team_label = self._team_label(organization_id, team_id)
        labels = self._person_labels(organization_id, [person_id for person_id, _ in members])

        signals: list[SignalRead] = []
        team_signal = self._capacity_signal(
            "team", team_id, team_label, team_result, start_date, end_date
        )
        if team_signal is not None:
            signals.append(team_signal)
        for person_id, result in members:
            member_signal = self._capacity_signal(
                "person", person_id, labels.get(person_id, "Unknown"), result, start_date, end_date
            )
            if member_signal is not None:
                signals.append(member_signal)

        imbalance = calculate_imbalance(
            [(person_id, result.utilization) for person_id, result in members]
        )
        if imbalance is not None:
            signals.append(
                self._imbalance_signal(team_id, team_label, imbalance, labels, start_date, end_date)
            )

        member_ids = [person_id for person_id, _ in members]
        remaining_by_person = {
            person_id: result.remaining_capacity for person_id, result in members
        }
        signals.extend(
            self._team_skill_holder_signals(
                organization_id,
                team_id,
                team_label,
                member_ids,
                remaining_by_person,
                start_date,
                end_date,
            )
        )
        return self._prioritize(signals)

    def get_project_signals(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[SignalRead]:
        _, _, signals = self._project_signals(organization_id, project_id, start_date, end_date)
        return self._prioritize(signals)

    def get_scenario_signals(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID
    ) -> list[SignalRead]:
        """Wraps ScenarioCalculationService.comparison(...).risks — never
        re-detects risk, only reclassifies each RiskRead into a SignalRead
        (severity + explanation + new-vs-existing + trend)."""
        comparison = self.scenario_calculation_service.comparison(organization_id, scenario_id)
        signals = [
            self._scenario_risk_signal(comparison.scenario, risk) for risk in comparison.risks
        ]
        return self._prioritize(signals)

    def get_team_summary(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        start_date: date,
        end_date: date,
        project_id: uuid.UUID | None = None,
        scenario_id: uuid.UUID | None = None,
    ) -> InsightsSummaryRead:
        team_signals = self.get_team_signals(organization_id, team_id, start_date, end_date)
        team_result, members = self.capacity_service.get_team_capacity(
            organization_id, team_id, start_date, end_date
        )
        team_label = self._team_label(organization_id, team_id)
        person_ids = [person_id for person_id, _ in members]
        labels = self._person_labels(organization_id, person_ids)

        utilization_distribution = sorted(
            (
                UtilizationPoint(
                    person_id=person_id,
                    label=labels.get(person_id, "Unknown"),
                    utilization=result.utilization,
                )
                for person_id, result in members
            ),
            key=lambda point: (point.utilization is None, -(point.utilization or ZERO)),
        )

        if project_id is not None:
            relevant_project_ids = [project_id]
        else:
            touched = self.allocation_repository.list_for_people(
                person_ids, start_date, end_date, organization_id
            )
            relevant_project_ids = sorted(
                {allocation.project_id for allocation in touched}, key=str
            )

        project_signals: list[SignalRead] = []
        concentration_areas: list[ConcentrationAreaRead] = []
        projects_under_pressure: list[ProjectPressureRead] = []
        for pid in relevant_project_ids:
            label, demand, signals = self._project_signals(
                organization_id, pid, start_date, end_date
            )
            project_signals.extend(signals)
            for signal in signals:
                if signal.type == "concentration_risk":
                    concentration_areas.append(
                        ConcentrationAreaRead(
                            project_id=pid,
                            project_label=label,
                            ratio=signal.concentration_ratio or ZERO,
                            top_contributor_ids=signal.concentration_person_ids or [],
                            top_contributor_labels=signal.concentration_person_labels or [],
                        )
                    )
                elif signal.type == "project_capacity_pressure":
                    projects_under_pressure.append(
                        ProjectPressureRead(
                            project_id=pid,
                            project_label=label,
                            severity=signal.severity,
                            demand_hours=demand.allocated_hours,
                            available_capacity=signal.effective_capacity or ZERO,
                            remaining_capacity=signal.remaining_capacity or ZERO,
                        )
                    )

        scenario_signals: list[SignalRead] = []
        scenario_delta: AggregateComparisonRead | None = None
        if scenario_id is not None:
            scenario_signals = self.get_scenario_signals(organization_id, scenario_id)
            scenario_delta = self.scenario_calculation_service.comparison(
                organization_id, scenario_id
            ).aggregate

        all_signals = team_signals + project_signals + scenario_signals
        signal_counts = SeverityCounts(
            critical=sum(1 for s in all_signals if s.severity == "critical"),
            warning=sum(1 for s in all_signals if s.severity == "warning"),
            info=sum(1 for s in all_signals if s.severity == "info"),
        )

        return InsightsSummaryRead(
            team_id=team_id,
            team_label=team_label,
            start_date=start_date,
            end_date=end_date,
            capacity=AggregateCapacityRead(
                start_date=team_result.start_date,
                end_date=team_result.end_date,
                gross_capacity=team_result.gross_capacity,
                unavailable_hours=team_result.unavailable_hours,
                effective_capacity=team_result.effective_capacity,
                allocated_hours=team_result.allocated_hours,
                remaining_capacity=team_result.remaining_capacity,
                utilization=team_result.utilization,
                over_allocation=team_result.over_allocation,
            ),
            signal_counts=signal_counts,
            utilization_distribution=utilization_distribution,
            concentration_areas=concentration_areas,
            projects_under_pressure=projects_under_pressure,
            scenario_id=scenario_id,
            scenario_delta=scenario_delta,
            scenario_new_risk_count=sum(1 for s in scenario_signals if s.is_new),
            scenario_existing_risk_count=sum(1 for s in scenario_signals if not s.is_new),
        )

    # -- Project signal assembly (shared by get_project_signals/get_team_summary)

    def _project_signals(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, start_date: date, end_date: date
    ) -> tuple[str, ProjectDemandResult, list[SignalRead]]:
        demand = self.capacity_service.get_project_demand(
            organization_id, project_id, start_date, end_date
        )
        label = self._project_label(organization_id, project_id)

        signals: list[SignalRead] = []
        concentration = calculate_concentration(list(demand.by_person))
        if concentration is not None:
            signals.append(
                self._concentration_signal(
                    organization_id, project_id, label, concentration, start_date, end_date
                )
            )
        pressure_signal = self._pressure_signal(
            organization_id, project_id, label, demand, start_date, end_date
        )
        if pressure_signal is not None:
            signals.append(pressure_signal)
        signals.extend(
            self._project_skill_signals(organization_id, project_id, label, start_date, end_date)
        )
        return label, demand, signals

    # -- Skill signal assembly (Phase 7) ---------------------------------------

    def _project_skill_signals(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        label: str,
        start_date: date,
        end_date: date,
    ) -> list[SignalRead]:
        """skill_gap (coverage shortfall) and single_skill_holder/
        skill_concentration (holder concentration) for every one of the
        project's ProjectSkillRequirement rows. The qualified population is
        ORG-SCOPED (everyone in this organization who holds the skill, not
        just people already allocated to this project — see
        docs/adr/0007-phase-7-skills-bottleneck-analysis.md for why a
        project has no fixed "eligible pool" to restrict this to; Phase 12
        adds the organization boundary on top of that same reasoning)."""
        requirements = self.project_skill_requirement_repository.list_for_project(
            project_id, organization_id
        )
        if not requirements:
            return []

        skill_ids = [requirement.skill_id for requirement in requirements]
        skills_by_id = {
            skill.id: skill
            for skill in self.skill_repository.list_by_ids(skill_ids, organization_id)
        }
        person_skills_by_skill: dict[uuid.UUID, list[PersonSkill]] = {}
        for row in self.person_skill_repository.list_for_skills(skill_ids, organization_id):
            person_skills_by_skill.setdefault(row.skill_id, []).append(row)

        all_person_ids = sorted(
            {row.person_id for rows in person_skills_by_skill.values() for row in rows}, key=str
        )
        remaining_by_person = self._remaining_capacity_by_person(
            organization_id, all_person_ids, start_date, end_date
        )
        person_labels = self._person_labels(organization_id, all_person_ids)

        signals: list[SignalRead] = []
        for requirement in requirements:
            skill = skills_by_id.get(requirement.skill_id)
            if skill is None or not skill.is_active:
                continue
            qualified = [
                QualifiedPerson(
                    person_id=row.person_id,
                    proficiency=row.proficiency,
                    remaining_capacity=remaining_by_person.get(row.person_id, ZERO),
                )
                for row in person_skills_by_skill.get(requirement.skill_id, [])
                if is_qualified(row.proficiency, requirement.minimum_proficiency)
            ]
            coverage = calculate_skill_coverage(requirement.required_hours, qualified)
            if coverage.gap_hours > ZERO:
                signals.append(
                    self._skill_gap_signal(
                        project_id, label, skill.id, skill.name, coverage, start_date, end_date
                    )
                )
            holder_signal = self._skill_holder_signal_from_concentration(
                "project",
                project_id,
                label,
                skill.id,
                skill.name,
                calculate_skill_concentration(qualified),
                person_labels,
                start_date,
                end_date,
            )
            if holder_signal is not None:
                signals.append(holder_signal)
        return signals

    def _team_skill_holder_signals(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        team_label: str,
        member_ids: Sequence[uuid.UUID],
        remaining_by_person: dict[uuid.UUID, Decimal],
        start_date: date,
        end_date: date,
    ) -> list[SignalRead]:
        """single_skill_holder/skill_concentration for every skill any team
        member holds — team scope has no required_hours (no skill_gap
        here), since only Project carries a stored skill demand."""
        person_skills = self.person_skill_repository.list_for_people(
            list(member_ids), organization_id
        )
        if not person_skills:
            return []
        skill_ids = sorted({row.skill_id for row in person_skills}, key=str)
        skills_by_id = {
            skill.id: skill
            for skill in self.skill_repository.list_by_ids(skill_ids, organization_id)
        }
        person_skills_by_skill: dict[uuid.UUID, list[PersonSkill]] = {}
        for row in person_skills:
            person_skills_by_skill.setdefault(row.skill_id, []).append(row)
        person_labels = self._person_labels(organization_id, list(member_ids))

        signals: list[SignalRead] = []
        for skill_id, rows in person_skills_by_skill.items():
            skill = skills_by_id.get(skill_id)
            if skill is None or not skill.is_active:
                continue
            qualified = [
                QualifiedPerson(
                    person_id=row.person_id,
                    proficiency=row.proficiency,
                    remaining_capacity=remaining_by_person.get(row.person_id, ZERO),
                )
                for row in rows
            ]
            holder_signal = self._skill_holder_signal_from_concentration(
                "team",
                team_id,
                team_label,
                skill.id,
                skill.name,
                calculate_skill_concentration(qualified),
                person_labels,
                start_date,
                end_date,
            )
            if holder_signal is not None:
                signals.append(holder_signal)
        return signals

    def _remaining_capacity_by_person(
        self,
        organization_id: uuid.UUID,
        person_ids: list[uuid.UUID],
        start_date: date,
        end_date: date,
    ) -> dict[uuid.UUID, Decimal]:
        facts_by_person = load_people_facts(
            self.schedule_repository,
            self.availability_repository,
            self.allocation_repository,
            person_ids,
            start_date,
            end_date,
            organization_id,
        )
        results: dict[uuid.UUID, Decimal] = {}
        for person_id, facts in facts_by_person.items():
            result = calculate_period_capacity(
                start_date,
                end_date,
                list(facts.schedules),
                list(facts.exceptions),
                list(facts.allocations),
            )
            results[person_id] = result.remaining_capacity
        return results

    # -- Signal builders ------------------------------------------------------

    def _capacity_signal(
        self,
        entity_type: EntityType,
        entity_id: uuid.UUID,
        label: str,
        result: PersonCapacityResult | TeamCapacityResult,
        start_date: date,
        end_date: date,
    ) -> SignalRead | None:
        period_days = (end_date - start_date).days + 1
        signal_type = classify_capacity_signal(
            effective_capacity=result.effective_capacity,
            remaining_capacity=result.remaining_capacity,
            over_allocation=result.over_allocation,
            period_days=period_days,
            low_capacity_threshold_per_day=self.low_capacity_threshold_hours_per_day,
        )
        if signal_type is None:
            return None
        explanation = self._capacity_explanation(
            signal_type,
            label,
            over_allocation=result.over_allocation,
            remaining_capacity=result.remaining_capacity,
            start_date=start_date,
            end_date=end_date,
        )
        return SignalRead(
            type=signal_type,
            severity=capacity_signal_severity(signal_type),
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=label,
            start_date=start_date,
            end_date=end_date,
            explanation=explanation,
            effective_capacity=result.effective_capacity,
            allocated_hours=result.allocated_hours,
            remaining_capacity=result.remaining_capacity,
            excess_hours=result.over_allocation if signal_type == "over_allocation" else None,
            utilization=result.utilization,
            threshold_hours_per_day=(
                self.low_capacity_threshold_hours_per_day if signal_type == "low_capacity" else None
            ),
            affected_person_ids=[entity_id] if entity_type == "person" else [],
        )

    def _pressure_signal(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        label: str,
        demand: ProjectDemandResult,
        start_date: date,
        end_date: date,
    ) -> SignalRead | None:
        """Reuses aggregate_team_capacity verbatim over the ad-hoc set of
        people allocated to the project — the same "any
        Sequence[PersonCapacityResult] is a team" seam ADR 0004 already
        exploited. No new formula: this treats the project's assigned
        people exactly like CapacityService.get_team_capacity treats a real
        team, so the signal reflects whether those people's OVERALL
        capacity picture (across all their commitments, not just this
        project) is under pressure."""
        person_ids = [entry.person_id for entry in demand.by_person]
        if not person_ids:
            return None
        facts_by_person = load_people_facts(
            self.schedule_repository,
            self.availability_repository,
            self.allocation_repository,
            person_ids,
            start_date,
            end_date,
            organization_id,
        )
        member_results = [
            calculate_period_capacity(
                start_date,
                end_date,
                list(facts.schedules),
                list(facts.exceptions),
                list(facts.allocations),
            )
            for facts in facts_by_person.values()
        ]
        aggregate = aggregate_team_capacity(start_date, end_date, member_results)
        period_days = (end_date - start_date).days + 1
        signal_type = classify_capacity_signal(
            effective_capacity=aggregate.effective_capacity,
            remaining_capacity=aggregate.remaining_capacity,
            over_allocation=aggregate.over_allocation,
            period_days=period_days,
            low_capacity_threshold_per_day=self.low_capacity_threshold_hours_per_day,
        )
        if signal_type is None:
            return None
        explanation = self._capacity_explanation(
            signal_type,
            label,
            over_allocation=aggregate.over_allocation,
            remaining_capacity=aggregate.remaining_capacity,
            start_date=start_date,
            end_date=end_date,
            demand_hours=demand.allocated_hours,
        )
        return SignalRead(
            type="project_capacity_pressure",
            severity=capacity_signal_severity(signal_type),
            entity_type="project",
            entity_id=project_id,
            entity_label=label,
            start_date=start_date,
            end_date=end_date,
            explanation=explanation,
            effective_capacity=aggregate.effective_capacity,
            allocated_hours=aggregate.allocated_hours,
            remaining_capacity=aggregate.remaining_capacity,
            excess_hours=aggregate.over_allocation if signal_type == "over_allocation" else None,
            utilization=aggregate.utilization,
            threshold_hours_per_day=(
                self.low_capacity_threshold_hours_per_day if signal_type == "low_capacity" else None
            ),
            affected_person_ids=sorted(person_ids, key=str),
        )

    def _concentration_signal(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        label: str,
        concentration: ConcentrationResult,
        start_date: date,
        end_date: date,
    ) -> SignalRead:
        contributor_labels_map = self._person_labels(
            organization_id, concentration.top_contributor_ids
        )
        contributor_labels = [
            contributor_labels_map.get(person_id, "Unknown")
            for person_id in concentration.top_contributor_ids
        ]
        explanation = (
            f"{label}'s top {len(concentration.top_contributor_ids)} contributors "
            f"({', '.join(contributor_labels)}) hold {self._format_percent(concentration.ratio)} "
            f"of its allocated hours {self._period_phrase(start_date, end_date)}."
        )
        return SignalRead(
            type="concentration_risk",
            severity="info",
            entity_type="project",
            entity_id=project_id,
            entity_label=label,
            start_date=start_date,
            end_date=end_date,
            explanation=explanation,
            concentration_ratio=concentration.ratio,
            concentration_person_ids=list(concentration.top_contributor_ids),
            concentration_person_labels=contributor_labels,
            affected_person_ids=list(concentration.top_contributor_ids),
        )

    def _imbalance_signal(
        self,
        team_id: uuid.UUID,
        team_label: str,
        imbalance: ImbalanceResult,
        labels: dict[uuid.UUID, str],
        start_date: date,
        end_date: date,
    ) -> SignalRead:
        min_label = labels.get(imbalance.min_person_id, "Unknown")
        max_label = labels.get(imbalance.max_person_id, "Unknown")
        min_pct = self._format_percent(imbalance.min_utilization)
        max_pct = self._format_percent(imbalance.max_utilization)
        explanation = (
            f"{team_label}'s utilization ranges from {min_pct} ({min_label}) to "
            f"{max_pct} ({max_label}) {self._period_phrase(start_date, end_date)}."
        )
        return SignalRead(
            type="capacity_imbalance",
            severity="info",
            entity_type="team",
            entity_id=team_id,
            entity_label=team_label,
            start_date=start_date,
            end_date=end_date,
            explanation=explanation,
            min_utilization=imbalance.min_utilization,
            min_utilization_person_id=imbalance.min_person_id,
            min_utilization_person_label=min_label,
            max_utilization=imbalance.max_utilization,
            max_utilization_person_id=imbalance.max_person_id,
            max_utilization_person_label=max_label,
            affected_person_ids=[imbalance.min_person_id, imbalance.max_person_id],
        )

    def _skill_gap_signal(
        self,
        project_id: uuid.UUID,
        label: str,
        skill_id: uuid.UUID,
        skill_label: str,
        coverage: SkillCoverageResult,
        start_date: date,
        end_date: date,
    ) -> SignalRead:
        """critical when there is literally no qualified available capacity
        (a confirmed blocker); warning when some exists but falls short of
        required_hours (worth a look, not yet fully blocked) — same
        critical-vs-warning split as capacity_signal_severity's confirmed-
        fact-vs-threshold distinction."""
        severity: Severity = "critical" if coverage.qualified_available_hours == ZERO else "warning"
        explanation = (
            f"{label} requires {self._format_hours(coverage.required_hours)} of {skill_label} "
            f"capacity {self._period_phrase(start_date, end_date)}, but only "
            f"{self._format_hours(coverage.qualified_available_hours)} of qualified available "
            f"capacity exists — a gap of {self._format_hours(coverage.gap_hours)}."
        )
        return SignalRead(
            type="skill_gap",
            severity=severity,
            entity_type="project",
            entity_id=project_id,
            entity_label=label,
            start_date=start_date,
            end_date=end_date,
            explanation=explanation,
            skill_id=skill_id,
            skill_label=skill_label,
            skill_required_hours=coverage.required_hours,
            skill_qualified_available_hours=coverage.qualified_available_hours,
            skill_coverage_ratio=coverage.coverage_ratio,
            skill_gap_hours=coverage.gap_hours,
            affected_person_ids=list(coverage.qualified_person_ids),
        )

    def _skill_holder_signal_from_concentration(
        self,
        entity_type: EntityType,
        entity_id: uuid.UUID,
        entity_label: str,
        skill_id: uuid.UUID,
        skill_label: str,
        concentration: SkillConcentrationResult | None,
        person_labels: dict[uuid.UUID, str],
        start_date: date,
        end_date: date,
    ) -> SignalRead | None:
        """holder_count == 1 -> single_skill_holder (warning: a single
        point of failure, a risk worth flagging even though nothing has
        gone wrong yet). holder_count == 2 -> skill_concentration (info: a
        structural observation, same severity Phase 5 gives
        concentration_risk). Mirrors calculate_skill_concentration's own
        existence-only gate — no invented percentage threshold."""
        if concentration is None:
            return None
        holder_labels = [
            person_labels.get(person_id, "Unknown")
            for person_id in concentration.top_contributor_ids
        ]
        if concentration.holder_count == 1:
            explanation = (
                f"Only one person ({holder_labels[0]}) currently has qualified available "
                f"capacity for {skill_label} on {entity_label} "
                f"{self._period_phrase(start_date, end_date)}."
            )
            return SignalRead(
                type="single_skill_holder",
                severity="warning",
                entity_type=entity_type,
                entity_id=entity_id,
                entity_label=entity_label,
                start_date=start_date,
                end_date=end_date,
                explanation=explanation,
                skill_id=skill_id,
                skill_label=skill_label,
                skill_holder_ids=list(concentration.top_contributor_ids),
                skill_holder_labels=holder_labels,
                skill_holder_ratio=concentration.ratio,
                affected_person_ids=list(concentration.top_contributor_ids),
            )
        explanation = (
            f"{skill_label}'s qualified available capacity on {entity_label} is held by just "
            f"{concentration.holder_count} people ({', '.join(holder_labels)}) "
            f"{self._period_phrase(start_date, end_date)}."
        )
        return SignalRead(
            type="skill_concentration",
            severity="info",
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=entity_label,
            start_date=start_date,
            end_date=end_date,
            explanation=explanation,
            skill_id=skill_id,
            skill_label=skill_label,
            skill_holder_ids=list(concentration.top_contributor_ids),
            skill_holder_labels=holder_labels,
            skill_holder_ratio=concentration.ratio,
            affected_person_ids=list(concentration.top_contributor_ids),
        )

    def _scenario_risk_signal(self, scenario: ScenarioRead, risk: RiskRead) -> SignalRead:
        severity = scenario_risk_severity(risk.type)
        trend = (
            None
            if risk.is_new
            else scenario_risk_trend(risk.type, risk.baseline_value, risk.scenario_value)
        )
        explanation = self._scenario_risk_explanation(risk, trend)
        return SignalRead(
            type="scenario_new_risk" if risk.is_new else "scenario_existing_risk",
            severity=severity,
            entity_type="person",
            entity_id=risk.person_id,
            entity_label=risk.label,
            start_date=scenario.baseline_start_date,
            end_date=scenario.baseline_end_date,
            explanation=explanation,
            scenario_id=scenario.id,
            is_new=risk.is_new,
            trend=trend,
            baseline_value=risk.baseline_value,
            scenario_value=risk.scenario_value,
            affected_person_ids=[risk.person_id],
        )

    # -- Explanation strings ---------------------------------------------------

    def _capacity_explanation(
        self,
        signal_type: CapacitySignalType,
        label: str,
        *,
        over_allocation: Decimal,
        remaining_capacity: Decimal,
        start_date: date,
        end_date: date,
        demand_hours: Decimal | None = None,
    ) -> str:
        period = self._period_phrase(start_date, end_date)
        suffix = (
            f", against {self._format_hours(demand_hours)} of demand on this project"
            if demand_hours is not None
            else ""
        )
        if signal_type == "over_allocation":
            return (
                f"{label} is allocated {self._format_hours(over_allocation)} more than "
                f"available capacity {period}{suffix}."
            )
        if signal_type == "zero_remaining_capacity":
            return f"{label} has no remaining capacity {period}{suffix}."
        return (
            f"{label} has only {self._format_hours(remaining_capacity)} of remaining capacity "
            f"{period}{suffix}, at or below the "
            f"{self._format_hours(self.low_capacity_threshold_hours_per_day)}/day threshold."
        )

    def _scenario_risk_explanation(self, risk: RiskRead, trend: ScenarioSignalTrend | None) -> str:
        if risk.type == "over_allocation":
            base = (
                f"{risk.label} becomes over-allocated by {self._format_hours(risk.scenario_value)} "
                "in this scenario."
            )
        else:
            base = f"{risk.label} would have no remaining capacity left in this scenario."
        if risk.is_new:
            return base
        return f"{base} This existing risk has {trend} compared to the baseline."

    # -- Labels ------------------------------------------------------------

    def _person_labels(
        self, organization_id: uuid.UUID, person_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        return {
            person.id: person.display_name
            for person in self.person_repository.list_by_ids(list(person_ids), organization_id)
        }

    def _team_label(self, organization_id: uuid.UUID, team_id: uuid.UUID) -> str:
        team = self.team_repository.get(team_id, organization_id)
        return team.name if team is not None else "Unknown"

    def _project_label(self, organization_id: uuid.UUID, project_id: uuid.UUID) -> str:
        project = self.project_repository.get(project_id, organization_id)
        return project.name if project is not None else "Unknown"

    # -- Formatting ----------------------------------------------------------

    def _period_phrase(self, start_date: date, end_date: date) -> str:
        return f"between {start_date.isoformat()} and {end_date.isoformat()}"

    def _format_hours(self, value: Decimal) -> str:
        return f"{value}h"

    def _format_percent(self, ratio: Decimal) -> str:
        return f"{(ratio * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)}%"

    # -- Deterministic priority order -----------------------------------------

    def _prioritize(self, signals: Sequence[SignalRead]) -> list[SignalRead]:
        def key(signal: SignalRead) -> tuple[int, int, int, str, str]:
            return (
                _SEVERITY_RANK[signal.severity],
                0 if signal.is_new else 1,
                _TYPE_RANK[signal.type],
                signal.entity_label,
                str(signal.entity_id),
            )

        return sorted(signals, key=key)

"""Orchestrates scenario calculation: load baseline facts, apply a
scenario's operations, run the UNMODIFIED Phase 2 engine over both, and
derive comparison/risk/impact from the results.

Holds no capacity formulas itself — see app/domain/capacity.py (reused
verbatim) and app/domain/scenario.py (the pure operation-application logic).
This service's job is exactly CapacityService's job (assemble repositories +
domain layer), plus the extra step of building the hypothetical state and
diffing two results. See docs/adr/0004-phase-4-scenario-planning.md.

No caching: results()/comparison() always re-read real baseline data and
recompute — see the ADR's "no caching" decision.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from app.core.exceptions import DomainValidationError, NotFoundError
from app.domain.capacity import ProjectDemandResult, aggregate_team_capacity
from app.domain.scenario import (
    AddAllocationOperation,
    AddHypotheticalResourceOperation,
    AdjustAllocationOperation,
    AvailabilityClearOperation,
    AvailabilityOverrideOperation,
    IdentifiedAllocationFact,
    MoveAllocationOperation,
    PlanningState,
    RemoveAllocationOperation,
    ShiftProjectOperation,
    apply_scenario_operations,
    person_capacity_from_state,
    project_demand_from_state,
)
from app.domain.scenario import (
    ScenarioOperation as DomainScenarioOperation,
)
from app.models.allocation import Allocation
from app.models.enums import ScenarioOperationType
from app.models.scenario import Scenario, ScenarioOperation
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.scenario import ScenarioOperationRepository, ScenarioRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.capacity import ProjectDailyDemandRead, ProjectDemandRead, ProjectPersonDemandRead
from app.schemas.scenario import (
    AddAllocationPayload,
    AddHypotheticalResourcePayload,
    AdjustAllocationPayload,
    AggregateCapacityRead,
    AggregateComparisonRead,
    AvailabilityClearPayload,
    AvailabilityOverridePayload,
    ImpactRead,
    MetricDelta,
    MoveAllocationPayload,
    PersonCapacityComparisonRead,
    PersonCapacitySnapshotRead,
    ProjectDemandComparisonRead,
    RemoveAllocationPayload,
    RiskRead,
    ScenarioComparisonRead,
    ScenarioOperationPayload,
    ScenarioRead,
    ScenarioResultsRead,
    ScenarioSnapshotRead,
    ShiftProjectPayload,
    operation_payload_from_dict,
)
from app.services.planning_facts import load_people_facts

ZERO = Decimal("0.00")


class _PreparedScenario:
    """Everything a results()/comparison() call needs, computed once by
    _prepare so the two entry points never duplicate the load-and-apply
    work."""

    def __init__(
        self,
        scenario: Scenario,
        baseline_state: PlanningState,
        scenario_state: PlanningState,
        person_ids: list[uuid.UUID],
        project_ids: list[uuid.UUID],
        hypothetical_ids: set[uuid.UUID],
        labels: dict[uuid.UUID, str],
        operations: list[ScenarioOperation],
    ) -> None:
        self.scenario = scenario
        self.baseline_state = baseline_state
        self.scenario_state = scenario_state
        self.person_ids = person_ids
        self.project_ids = project_ids
        self.hypothetical_ids = hypothetical_ids
        self.labels = labels
        self.operations = operations


class ScenarioCalculationService:
    def __init__(
        self,
        scenario_repository: ScenarioRepository,
        operation_repository: ScenarioOperationRepository,
        person_repository: PersonRepository,
        project_repository: ProjectRepository,
        allocation_repository: AllocationRepository,
        schedule_repository: WorkingScheduleRepository,
        availability_repository: AvailabilityExceptionRepository,
        team_membership_repository: TeamMembershipRepository,
    ) -> None:
        self.scenario_repository = scenario_repository
        self.operation_repository = operation_repository
        self.person_repository = person_repository
        self.project_repository = project_repository
        self.allocation_repository = allocation_repository
        self.schedule_repository = schedule_repository
        self.availability_repository = availability_repository
        self.team_membership_repository = team_membership_repository

    # -- Public entry points --------------------------------------------

    def results(self, organization_id: uuid.UUID, scenario_id: uuid.UUID) -> ScenarioResultsRead:
        prepared = self._prepare(organization_id, scenario_id)
        start, end = prepared.scenario.baseline_start_date, prepared.scenario.baseline_end_date

        baseline_people = [
            self._person_snapshot(prepared, prepared.baseline_state, pid, start, end)
            for pid in prepared.person_ids
        ]
        scenario_people = [
            self._person_snapshot(prepared, prepared.scenario_state, pid, start, end)
            for pid in prepared.person_ids
        ]
        ids = prepared.person_ids
        baseline_aggregate = self._aggregate(prepared.baseline_state, ids, start, end)
        scenario_aggregate = self._aggregate(prepared.scenario_state, ids, start, end)

        baseline_projects = [
            self._project_read(
                project_demand_from_state(prepared.baseline_state, pid, start, end), pid
            )
            for pid in prepared.project_ids
        ]
        scenario_projects = [
            self._project_read(
                project_demand_from_state(prepared.scenario_state, pid, start, end), pid
            )
            for pid in prepared.project_ids
        ]

        return ScenarioResultsRead(
            scenario=ScenarioRead.model_validate(prepared.scenario),
            baseline=ScenarioSnapshotRead(
                aggregate=baseline_aggregate, people=baseline_people, projects=baseline_projects
            ),
            scenario_state=ScenarioSnapshotRead(
                aggregate=scenario_aggregate, people=scenario_people, projects=scenario_projects
            ),
        )

    def comparison(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID
    ) -> ScenarioComparisonRead:
        prepared = self._prepare(organization_id, scenario_id)
        start, end = prepared.scenario.baseline_start_date, prepared.scenario.baseline_end_date

        people_comparisons = [
            self._person_comparison(prepared, pid, start, end) for pid in prepared.person_ids
        ]
        project_comparisons = [
            self._project_comparison(prepared, pid, start, end) for pid in prepared.project_ids
        ]

        ids = prepared.person_ids
        baseline_aggregate = self._aggregate(prepared.baseline_state, ids, start, end)
        scenario_aggregate = self._aggregate(prepared.scenario_state, ids, start, end)
        over_allocated_baseline = sum(
            1 for c in people_comparisons if c.baseline.over_allocation > ZERO
        )
        over_allocated_scenario = sum(
            1 for c in people_comparisons if c.scenario.over_allocation > ZERO
        )

        risks = self._risks(people_comparisons)
        impact = self._impact(organization_id, prepared)

        return ScenarioComparisonRead(
            scenario=ScenarioRead.model_validate(prepared.scenario),
            aggregate=AggregateComparisonRead(
                baseline=baseline_aggregate,
                scenario=scenario_aggregate,
                utilization=_delta(baseline_aggregate.utilization, scenario_aggregate.utilization),
                remaining_capacity=_delta_nonnull(
                    baseline_aggregate.remaining_capacity, scenario_aggregate.remaining_capacity
                ),
                over_allocation=_delta_nonnull(
                    baseline_aggregate.over_allocation, scenario_aggregate.over_allocation
                ),
                over_allocated_people=MetricDelta[int](
                    baseline=over_allocated_baseline,
                    scenario=over_allocated_scenario,
                    delta=over_allocated_scenario - over_allocated_baseline,
                ),
            ),
            people=people_comparisons,
            projects=project_comparisons,
            risks=risks,
            impact=impact,
        )

    # -- Preparation: baseline + scenario PlanningState ------------------

    def _prepare(self, organization_id: uuid.UUID, scenario_id: uuid.UUID) -> _PreparedScenario:
        scenario = self.scenario_repository.get(scenario_id, organization_id)
        if scenario is None:
            raise NotFoundError("Scenario", scenario_id)
        operations = self.operation_repository.list_for_scenario(scenario_id)

        hypothetical_ids = {
            op.id
            for op in operations
            if op.operation_type == ScenarioOperationType.ADD_HYPOTHETICAL_RESOURCE
        }
        real_person_ids, project_ids = self._collect_scope(
            organization_id,
            operations,
            hypothetical_ids,
            scenario.baseline_start_date,
            scenario.baseline_end_date,
        )

        baseline_state = self._load_baseline_state(
            organization_id,
            real_person_ids,
            scenario.baseline_start_date,
            scenario.baseline_end_date,
        )
        domain_operations = [self._to_domain_operation(op) for op in operations]
        scenario_state = apply_scenario_operations(baseline_state, domain_operations)

        labels = self._labels(organization_id, real_person_ids, operations)
        person_ids = self._all_relevant_person_ids(baseline_state, scenario_state, real_person_ids)

        return _PreparedScenario(
            scenario=scenario,
            baseline_state=baseline_state,
            scenario_state=scenario_state,
            person_ids=person_ids,
            project_ids=sorted(project_ids, key=str),
            hypothetical_ids=hypothetical_ids,
            labels=labels,
            operations=operations,
        )

    def _collect_scope(
        self,
        organization_id: uuid.UUID,
        operations: Sequence[ScenarioOperation],
        hypothetical_ids: set[uuid.UUID],
        start_date: date,
        end_date: date,
    ) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        """Every real person_id and project_id an operation references,
        directly or via a real allocation it points at — PLUS every other
        person already allocated to a referenced project. That last part is
        not optional: project_demand_from_state sums every allocation in
        the PlanningState for a project (app/domain/scenario.py), so if a
        project's existing contributors were left out of baseline_state,
        the project's baseline demand total would silently exclude their
        hours. Bounded by the scenario's own operation count plus the full
        membership of any project it touches — not by total system size
        (CLAUDE.md §26)."""
        real_person_ids: set[uuid.UUID] = set()
        project_ids: set[uuid.UUID] = set()

        def add_person(person_id: uuid.UUID) -> None:
            if person_id not in hypothetical_ids:
                real_person_ids.add(person_id)

        for op in operations:
            payload = operation_payload_from_dict(op.operation_type, op.payload)
            if isinstance(payload, AddAllocationPayload):
                add_person(payload.person_id)
                project_ids.add(payload.project_id)
            elif isinstance(payload, AdjustAllocationPayload | RemoveAllocationPayload):
                allocation = self._require_allocation(organization_id, payload.allocation_id)
                real_person_ids.add(allocation.person_id)
                project_ids.add(allocation.project_id)
            elif isinstance(payload, MoveAllocationPayload):
                allocation = self._require_allocation(organization_id, payload.allocation_id)
                real_person_ids.add(allocation.person_id)
                project_ids.add(allocation.project_id)
                add_person(payload.to_person_id)
            elif isinstance(payload, ShiftProjectPayload):
                project_ids.add(payload.project_id)
            elif isinstance(payload, AvailabilityOverridePayload | AvailabilityClearPayload):
                add_person(payload.person_id)
            # AddHypotheticalResourcePayload references nothing pre-existing.

        for project_id in project_ids:
            for allocation in self.allocation_repository.list_for_project(
                project_id, start_date, end_date, organization_id
            ):
                real_person_ids.add(allocation.person_id)

        return real_person_ids, project_ids

    def _require_allocation(
        self, organization_id: uuid.UUID, allocation_id: uuid.UUID
    ) -> Allocation:
        allocation = self.allocation_repository.get(allocation_id, organization_id)
        if allocation is None:
            raise DomainValidationError(
                f"Cannot recalculate this scenario: allocation {allocation_id} referenced by "
                "one of its operations no longer exists in the current plan."
            )
        return allocation

    def _load_baseline_state(
        self,
        organization_id: uuid.UUID,
        person_ids: set[uuid.UUID],
        start_date: date,
        end_date: date,
    ) -> PlanningState:
        """Delegates to the same load_people_facts every capacity/insight
        calculation uses (app/services/planning_facts.py) rather than
        duplicating its batched-query shape — one org-scoped interception
        point for schedule/availability/allocation facts, not two."""
        ids = list(person_ids)
        facts_by_person = load_people_facts(
            self.schedule_repository,
            self.availability_repository,
            self.allocation_repository,
            ids,
            start_date,
            end_date,
            organization_id,
        )

        schedules = {pid: facts_by_person[pid].schedules for pid in ids}
        exceptions = {pid: facts_by_person[pid].exceptions for pid in ids}
        allocation_rows = self.allocation_repository.list_for_people(
            ids, start_date, end_date, organization_id
        )
        allocations = tuple(
            IdentifiedAllocationFact(
                id=row.id,
                person_id=row.person_id,
                project_id=row.project_id,
                start_date=row.start_date,
                end_date=row.end_date,
                allocation_hours=row.allocation_hours,
            )
            for row in allocation_rows
        )
        return PlanningState(schedules=schedules, exceptions=exceptions, allocations=allocations)

    def _to_domain_operation(self, operation: ScenarioOperation) -> DomainScenarioOperation:
        payload: ScenarioOperationPayload = operation_payload_from_dict(
            operation.operation_type, operation.payload
        )
        if isinstance(payload, AddAllocationPayload):
            return AddAllocationOperation(
                id=operation.id,
                sequence=operation.sequence,
                person_id=payload.person_id,
                project_id=payload.project_id,
                hours=payload.hours,
                start_date=payload.start_date,
                end_date=payload.end_date,
            )
        if isinstance(payload, AdjustAllocationPayload):
            return AdjustAllocationOperation(
                id=operation.id,
                sequence=operation.sequence,
                allocation_id=payload.allocation_id,
                hours=payload.hours,
                start_date=payload.start_date,
                end_date=payload.end_date,
            )
        if isinstance(payload, RemoveAllocationPayload):
            return RemoveAllocationOperation(
                id=operation.id, sequence=operation.sequence, allocation_id=payload.allocation_id
            )
        if isinstance(payload, MoveAllocationPayload):
            return MoveAllocationOperation(
                id=operation.id,
                sequence=operation.sequence,
                allocation_id=payload.allocation_id,
                to_person_id=payload.to_person_id,
                hours=payload.hours,
            )
        if isinstance(payload, ShiftProjectPayload):
            return ShiftProjectOperation(
                id=operation.id,
                sequence=operation.sequence,
                project_id=payload.project_id,
                day_offset=payload.day_offset,
            )
        if isinstance(payload, AvailabilityOverridePayload):
            return AvailabilityOverrideOperation(
                id=operation.id,
                sequence=operation.sequence,
                person_id=payload.person_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                hours=payload.hours,
            )
        if isinstance(payload, AvailabilityClearPayload):
            return AvailabilityClearOperation(
                id=operation.id,
                sequence=operation.sequence,
                person_id=payload.person_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
            )
        # AddHypotheticalResourcePayload — the only remaining union member.
        return AddHypotheticalResourceOperation(
            id=operation.id,
            sequence=operation.sequence,
            label=payload.label,
            hours_per_week=payload.hours_per_week,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )

    def _labels(
        self,
        organization_id: uuid.UUID,
        real_person_ids: set[uuid.UUID],
        operations: Sequence[ScenarioOperation],
    ) -> dict[uuid.UUID, str]:
        labels = {
            person.id: person.display_name
            for person in self.person_repository.list_by_ids(
                list(real_person_ids), organization_id
            )
        }
        for op in operations:
            if op.operation_type == ScenarioOperationType.ADD_HYPOTHETICAL_RESOURCE:
                payload = operation_payload_from_dict(op.operation_type, op.payload)
                assert isinstance(payload, AddHypotheticalResourcePayload)  # noqa: S101
                labels[op.id] = payload.label
        return labels

    def _all_relevant_person_ids(
        self,
        baseline_state: PlanningState,
        scenario_state: PlanningState,
        real_person_ids: set[uuid.UUID],
    ) -> list[uuid.UUID]:
        ids = set(real_person_ids)
        ids.update(baseline_state.schedules.keys())
        ids.update(scenario_state.schedules.keys())
        ids.update(a.person_id for a in baseline_state.allocations)
        ids.update(a.person_id for a in scenario_state.allocations)
        return sorted(ids, key=str)

    # -- Snapshot / comparison assembly ----------------------------------

    def _person_snapshot(
        self,
        prepared: _PreparedScenario,
        state: PlanningState,
        person_id: uuid.UUID,
        start: date,
        end: date,
    ) -> PersonCapacitySnapshotRead:
        result = person_capacity_from_state(state, person_id, start, end)
        return PersonCapacitySnapshotRead(
            person_id=person_id,
            label=prepared.labels.get(person_id, "Unknown"),
            is_hypothetical=person_id in prepared.hypothetical_ids,
            start_date=result.start_date,
            end_date=result.end_date,
            gross_capacity=result.gross_capacity,
            unavailable_hours=result.unavailable_hours,
            effective_capacity=result.effective_capacity,
            allocated_hours=result.allocated_hours,
            remaining_capacity=result.remaining_capacity,
            utilization=result.utilization,
            over_allocation=result.over_allocation,
        )

    def _aggregate(
        self, state: PlanningState, person_ids: Sequence[uuid.UUID], start: date, end: date
    ) -> AggregateCapacityRead:
        results = [person_capacity_from_state(state, pid, start, end) for pid in person_ids]
        aggregate = aggregate_team_capacity(start, end, results)
        return AggregateCapacityRead(
            start_date=aggregate.start_date,
            end_date=aggregate.end_date,
            gross_capacity=aggregate.gross_capacity,
            unavailable_hours=aggregate.unavailable_hours,
            effective_capacity=aggregate.effective_capacity,
            allocated_hours=aggregate.allocated_hours,
            remaining_capacity=aggregate.remaining_capacity,
            utilization=aggregate.utilization,
            over_allocation=aggregate.over_allocation,
        )

    def _project_read(
        self, result: ProjectDemandResult, project_id: uuid.UUID
    ) -> ProjectDemandRead:
        return ProjectDemandRead(
            project_id=project_id,
            start_date=result.start_date,
            end_date=result.end_date,
            allocated_hours=result.allocated_hours,
            allocated_people=result.allocated_people,
            daily_breakdown=[
                ProjectDailyDemandRead(date=d.date, allocated_hours=d.allocated_hours)
                for d in result.daily_breakdown
            ],
            by_person=[
                ProjectPersonDemandRead(person_id=p.person_id, allocated_hours=p.allocated_hours)
                for p in result.by_person
            ],
        )

    def _person_comparison(
        self, prepared: _PreparedScenario, person_id: uuid.UUID, start: date, end: date
    ) -> PersonCapacityComparisonRead:
        baseline = self._person_snapshot(prepared, prepared.baseline_state, person_id, start, end)
        scenario = self._person_snapshot(prepared, prepared.scenario_state, person_id, start, end)
        return PersonCapacityComparisonRead(
            person_id=person_id,
            label=prepared.labels.get(person_id, "Unknown"),
            is_hypothetical=person_id in prepared.hypothetical_ids,
            baseline=baseline,
            scenario=scenario,
            utilization=_delta(baseline.utilization, scenario.utilization),
            remaining_capacity=_delta_nonnull(
                baseline.remaining_capacity, scenario.remaining_capacity
            ),
            over_allocation=_delta_nonnull(baseline.over_allocation, scenario.over_allocation),
            newly_over_allocated=(
                baseline.over_allocation == ZERO and scenario.over_allocation > ZERO
            ),
        )

    def _project_comparison(
        self, prepared: _PreparedScenario, project_id: uuid.UUID, start: date, end: date
    ) -> ProjectDemandComparisonRead:
        baseline = self._project_read(
            project_demand_from_state(prepared.baseline_state, project_id, start, end), project_id
        )
        scenario = self._project_read(
            project_demand_from_state(prepared.scenario_state, project_id, start, end), project_id
        )
        return ProjectDemandComparisonRead(
            project_id=project_id,
            baseline=baseline,
            scenario=scenario,
            allocated_hours=_delta_nonnull(baseline.allocated_hours, scenario.allocated_hours),
        )

    def _risks(self, people: Sequence[PersonCapacityComparisonRead]) -> list[RiskRead]:
        """Only objective facts the engine already computed — over-allocation
        and exactly-zero remaining capacity. No invented "unmet project
        demand" or utilization-threshold risk (that judgment call stays a
        frontend presentation concern, same as Phase 3's AT_CAPACITY_MIN —
        see docs/adr/0004-phase-4-scenario-planning.md)."""
        risks: list[RiskRead] = []
        for comparison in people:
            if comparison.scenario.over_allocation > ZERO:
                risks.append(
                    RiskRead(
                        type="over_allocation",
                        person_id=comparison.person_id,
                        label=comparison.label,
                        is_new=comparison.newly_over_allocated,
                        baseline_value=comparison.baseline.over_allocation,
                        scenario_value=comparison.scenario.over_allocation,
                    )
                )
            elif (
                comparison.scenario.remaining_capacity == ZERO
                and comparison.scenario.effective_capacity > ZERO
            ):
                # Exactly at capacity — distinct from (and never co-reported
                # with) over_allocation, which already covers remaining < 0.
                risks.append(
                    RiskRead(
                        type="zero_remaining_capacity",
                        person_id=comparison.person_id,
                        label=comparison.label,
                        is_new=comparison.baseline.remaining_capacity > ZERO,
                        baseline_value=comparison.baseline.remaining_capacity,
                        scenario_value=comparison.scenario.remaining_capacity,
                    )
                )
        return sorted(risks, key=lambda r: (not r.is_new, r.person_id.hex))

    def _impact(self, organization_id: uuid.UUID, prepared: _PreparedScenario) -> ImpactRead:
        team_ids = {
            membership.team_id
            for membership in self.team_membership_repository.list_for_people(
                prepared.person_ids, organization_id
            )
        }

        dates: list[date] = []
        all_allocations = (
            *prepared.baseline_state.allocations,
            *prepared.scenario_state.allocations,
        )
        for allocation in all_allocations:
            dates.append(allocation.start_date)
            dates.append(allocation.end_date)
        for op in prepared.operations:
            payload = operation_payload_from_dict(op.operation_type, op.payload)
            start_date = getattr(payload, "start_date", None)
            end_date = getattr(payload, "end_date", None)
            if start_date is not None:
                dates.append(start_date)
            if end_date is not None:
                dates.append(end_date)

        return ImpactRead(
            affected_people=prepared.person_ids,
            affected_projects=prepared.project_ids,
            affected_teams=sorted(team_ids, key=str),
            affected_start_date=min(dates) if dates else None,
            affected_end_date=max(dates) if dates else None,
        )


def _delta(baseline: Decimal | None, scenario: Decimal | None) -> MetricDelta[Decimal | None]:
    """For utilization only — None whenever effective capacity is 0 on
    either side (see docs/domain-concepts.md#capacity-engine-phase-2)."""
    delta = scenario - baseline if baseline is not None and scenario is not None else None
    return MetricDelta[Decimal | None](baseline=baseline, scenario=scenario, delta=delta)


def _delta_nonnull(baseline: Decimal, scenario: Decimal) -> MetricDelta[Decimal]:
    """For remaining_capacity/over_allocation/allocated_hours — the domain
    engine never returns None for these (only utilization can be None)."""
    return MetricDelta[Decimal](baseline=baseline, scenario=scenario, delta=scenario - baseline)

"""Pure scenario-planning transformation logic (CLAUDE.md §10, Phase 4).

No SQLAlchemy, no FastAPI, no I/O — same discipline as app/domain/capacity.py,
which this module reuses completely unmodified. A Scenario never gets its
own copy of the capacity formulas: it builds a hypothetical PlanningState
(this module's job) and hands it to the exact same calculate_period_capacity
/ aggregate_team_capacity / calculate_project_demand functions Phase 2
already validated (person_capacity_from_state / project_demand_from_state
below are thin adapters, not a second engine).

See docs/adr/0004-phase-4-scenario-planning.md for why these 8 operation
types were chosen and how conflicts between operations are resolved
(sequence order; a later operation sees the effect of every earlier one).
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.domain.capacity import (
    AllocationFact,
    AvailabilityExceptionFact,
    PersonCapacityResult,
    ProjectAllocationFact,
    ProjectDemandResult,
    ScheduleFact,
    calculate_period_capacity,
    calculate_project_demand,
)

_HYPOTHETICAL_SCHEDULE_CREATED_AT = datetime(1970, 1, 1, tzinfo=UTC)
"""ScheduleFact.created_at exists only as a tie-break for overlapping
schedules (see calculate_daily_capacity._scheduled_hours_for_date). A
hypothetical resource has exactly one synthetic schedule, so the tie-break
never activates; this fixed value just satisfies the dataclass's type."""


# ---------------------------------------------------------------------------
# Planning state — the hypothetical counterpart of the facts
# app/services/planning_facts.py builds from real ORM rows
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentifiedAllocationFact:
    """An AllocationFact that still knows which allocation, person, and
    project it belongs to. app/domain/capacity.AllocationFact deliberately
    strips this identity (it doesn't need it to calculate); the scenario
    layer needs it back because operations target a specific allocation
    (adjust/remove/move) or a specific project (shift_project) by id, and
    move_allocation changes which person an allocation belongs to.
    """

    id: uuid.UUID
    person_id: uuid.UUID
    project_id: uuid.UUID
    start_date: date
    end_date: date
    allocation_hours: Decimal

    def to_fact(self) -> AllocationFact:
        return AllocationFact(
            start_date=self.start_date,
            end_date=self.end_date,
            allocation_hours=self.allocation_hours,
        )


@dataclass(frozen=True)
class PlanningState:
    """A full hypothetical (or baseline) planning snapshot.

    schedules/exceptions are keyed by person_id (real or, for a person only
    introduced by add_hypothetical_resource, that operation's own id — see
    AddHypotheticalResourceOperation). allocations is a single flat tuple
    (not grouped by person) because move_allocation changes an allocation's
    owner and shift_project looks allocations up by project_id across every
    person at once; grouping by person up front would need re-grouping on
    every move.

    Immutable by construction (frozen dataclass, tuple fields) — every
    transformation in this module returns a new PlanningState rather than
    mutating one, which is what makes "the baseline never changes" checkable
    by simple equality/identity in tests.
    """

    schedules: Mapping[uuid.UUID, tuple[ScheduleFact, ...]] = field(
        default_factory=lambda: dict[uuid.UUID, tuple[ScheduleFact, ...]]()
    )
    exceptions: Mapping[uuid.UUID, tuple[AvailabilityExceptionFact, ...]] = field(
        default_factory=lambda: dict[uuid.UUID, tuple[AvailabilityExceptionFact, ...]]()
    )
    allocations: tuple[IdentifiedAllocationFact, ...] = field(default_factory=tuple)


def person_capacity_from_state(
    state: PlanningState, person_id: uuid.UUID, start_date: date, end_date: date
) -> PersonCapacityResult:
    """Adapter, not a calculation: pulls person_id's facts out of state and
    hands them to the unmodified Phase 2 engine."""
    allocations = [a.to_fact() for a in state.allocations if a.person_id == person_id]
    return calculate_period_capacity(
        start_date,
        end_date,
        list(state.schedules.get(person_id, ())),
        list(state.exceptions.get(person_id, ())),
        allocations,
    )


def project_demand_from_state(
    state: PlanningState, project_id: uuid.UUID, start_date: date, end_date: date
) -> ProjectDemandResult:
    """Adapter, not a calculation — see person_capacity_from_state."""
    facts = [
        ProjectAllocationFact(person_id=a.person_id, allocation=a.to_fact())
        for a in state.allocations
        if a.project_id == project_id
    ]
    return calculate_project_demand(start_date, end_date, facts)


# ---------------------------------------------------------------------------
# Operations — typed, immutable, one dataclass per operation_type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AddAllocationOperation:
    id: uuid.UUID
    sequence: int
    person_id: uuid.UUID
    project_id: uuid.UUID
    hours: Decimal
    start_date: date
    end_date: date


@dataclass(frozen=True)
class AdjustAllocationOperation:
    id: uuid.UUID
    sequence: int
    allocation_id: uuid.UUID
    hours: Decimal | None
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class RemoveAllocationOperation:
    id: uuid.UUID
    sequence: int
    allocation_id: uuid.UUID


@dataclass(frozen=True)
class MoveAllocationOperation:
    id: uuid.UUID
    sequence: int
    allocation_id: uuid.UUID
    to_person_id: uuid.UUID
    hours: Decimal | None
    """None = move the whole allocation (its person_id simply changes). A
    value < the allocation's current hours splits it: the original
    allocation keeps (current - hours) and a new allocation (this
    operation's id) is created for to_person_id with `hours`."""


@dataclass(frozen=True)
class ShiftProjectOperation:
    id: uuid.UUID
    sequence: int
    project_id: uuid.UUID
    day_offset: int
    """Shifts every allocation on project_id BY THIS POINT IN THE OPERATION
    SEQUENCE by day_offset days — an add_allocation on the same project
    later in sequence is unaffected; one earlier is shifted too. See the
    ADR's conflict-resolution section."""


@dataclass(frozen=True)
class AvailabilityOverrideOperation:
    id: uuid.UUID
    sequence: int
    person_id: uuid.UUID
    start_date: date
    end_date: date
    hours: Decimal | None
    """None = fully unavailable for the window; a value = available that
    many hours/day, same convention as AvailabilityExceptionFact.hours."""


@dataclass(frozen=True)
class AvailabilityClearOperation:
    id: uuid.UUID
    sequence: int
    person_id: uuid.UUID
    start_date: date
    end_date: date
    """Removes/clips any baseline-or-earlier-scenario exception overlapping
    this window, without adding a replacement — models "returned from leave
    early" (the normal working schedule applies again for this window)."""


@dataclass(frozen=True)
class AddHypotheticalResourceOperation:
    id: uuid.UUID
    sequence: int
    label: str
    hours_per_week: Decimal
    start_date: date
    end_date: date
    """Creates a virtual person — this operation's own id — with a synthetic
    Mon-Fri schedule spreading hours_per_week evenly across 5 days, in
    effect for [start_date, end_date]. No Person row is ever created; later
    add_allocation operations in the same scenario reference this id as
    their person_id."""


ScenarioOperation = (
    AddAllocationOperation
    | AdjustAllocationOperation
    | RemoveAllocationOperation
    | MoveAllocationOperation
    | ShiftProjectOperation
    | AvailabilityOverrideOperation
    | AvailabilityClearOperation
    | AddHypotheticalResourceOperation
)


# ---------------------------------------------------------------------------
# Applying operations
# ---------------------------------------------------------------------------


def _clip_exceptions(
    exceptions: tuple[AvailabilityExceptionFact, ...], start: date, end: date
) -> tuple[AvailabilityExceptionFact, ...]:
    """Removes [start, end] from every exception in exceptions, splitting an
    exception that only partially overlaps into its surviving remainder(s).
    Shared by AvailabilityOverrideOperation (clip, then add a replacement)
    and AvailabilityClearOperation (clip only) — see their docstrings."""
    result: list[AvailabilityExceptionFact] = []
    for exception in exceptions:
        if exception.end_date < start or exception.start_date > end:
            result.append(exception)
            continue
        if exception.start_date < start:
            result.append(
                AvailabilityExceptionFact(
                    start_date=exception.start_date,
                    end_date=start - timedelta(days=1),
                    hours=exception.hours,
                )
            )
        if exception.end_date > end:
            result.append(
                AvailabilityExceptionFact(
                    start_date=end + timedelta(days=1),
                    end_date=exception.end_date,
                    hours=exception.hours,
                )
            )
    return tuple(result)


def _apply_one(state: PlanningState, operation: ScenarioOperation) -> PlanningState:
    if isinstance(operation, AddAllocationOperation):
        new_allocation = IdentifiedAllocationFact(
            id=operation.id,
            person_id=operation.person_id,
            project_id=operation.project_id,
            start_date=operation.start_date,
            end_date=operation.end_date,
            allocation_hours=operation.hours,
        )
        return replace(state, allocations=(*state.allocations, new_allocation))

    if isinstance(operation, AdjustAllocationOperation):
        found = False
        allocations: list[IdentifiedAllocationFact] = []
        for allocation in state.allocations:
            if allocation.id != operation.allocation_id:
                allocations.append(allocation)
                continue
            found = True
            new_hours = (
                operation.hours if operation.hours is not None else allocation.allocation_hours
            )
            new_start = (
                operation.start_date if operation.start_date is not None else allocation.start_date
            )
            new_end = operation.end_date if operation.end_date is not None else allocation.end_date
            allocations.append(
                replace(
                    allocation,
                    allocation_hours=new_hours,
                    start_date=new_start,
                    end_date=new_end,
                )
            )
        if not found:
            raise ValueError(f"adjust_allocation: unknown allocation_id {operation.allocation_id}")
        return replace(state, allocations=tuple(allocations))

    if isinstance(operation, RemoveAllocationOperation):
        remaining = tuple(a for a in state.allocations if a.id != operation.allocation_id)
        if len(remaining) == len(state.allocations):
            raise ValueError(f"remove_allocation: unknown allocation_id {operation.allocation_id}")
        return replace(state, allocations=remaining)

    if isinstance(operation, MoveAllocationOperation):
        target = next((a for a in state.allocations if a.id == operation.allocation_id), None)
        if target is None:
            raise ValueError(f"move_allocation: unknown allocation_id {operation.allocation_id}")
        move_hours = operation.hours if operation.hours is not None else target.allocation_hours
        if move_hours > target.allocation_hours:
            raise ValueError(
                f"move_allocation: cannot move {move_hours}h from an allocation of "
                f"{target.allocation_hours}h"
            )
        remainder_hours = target.allocation_hours - move_hours
        allocations = [a for a in state.allocations if a.id != target.id]
        if remainder_hours > 0:
            allocations.append(replace(target, allocation_hours=remainder_hours))
            moved = IdentifiedAllocationFact(
                id=operation.id,
                person_id=operation.to_person_id,
                project_id=target.project_id,
                start_date=target.start_date,
                end_date=target.end_date,
                allocation_hours=move_hours,
            )
        else:
            moved = replace(target, person_id=operation.to_person_id)
        allocations.append(moved)
        return replace(state, allocations=tuple(allocations))

    if isinstance(operation, ShiftProjectOperation):
        offset = timedelta(days=operation.day_offset)
        shifted = tuple(
            replace(a, start_date=a.start_date + offset, end_date=a.end_date + offset)
            if a.project_id == operation.project_id
            else a
            for a in state.allocations
        )
        return replace(state, allocations=shifted)

    if isinstance(operation, AvailabilityOverrideOperation):
        existing = state.exceptions.get(operation.person_id, ())
        clipped = _clip_exceptions(existing, operation.start_date, operation.end_date)
        override = AvailabilityExceptionFact(
            start_date=operation.start_date, end_date=operation.end_date, hours=operation.hours
        )
        exceptions = {**state.exceptions, operation.person_id: (*clipped, override)}
        return replace(state, exceptions=exceptions)

    if isinstance(operation, AvailabilityClearOperation):
        existing = state.exceptions.get(operation.person_id, ())
        clipped = _clip_exceptions(existing, operation.start_date, operation.end_date)
        exceptions = {**state.exceptions, operation.person_id: clipped}
        return replace(state, exceptions=exceptions)

    # AddHypotheticalResourceOperation — the only remaining member of the
    # ScenarioOperation union once every branch above has returned.
    per_day = (operation.hours_per_week / 5).quantize(Decimal("0.01"))
    schedule = ScheduleFact(
        effective_start_date=operation.start_date,
        effective_end_date=operation.end_date,
        entries={weekday: per_day for weekday in range(5)},
        created_at=_HYPOTHETICAL_SCHEDULE_CREATED_AT,
    )
    schedules = {**state.schedules, operation.id: (schedule,)}
    return replace(state, schedules=schedules)


def apply_scenario_operations(
    baseline: PlanningState, operations: Sequence[ScenarioOperation]
) -> PlanningState:
    """Returns a NEW PlanningState reflecting every operation in
    sequence order — never mutates baseline (every branch in _apply_one
    calls dataclasses.replace, which builds a new PlanningState/tuple/dict;
    baseline's own fields are never assigned into). This is the invariant
    the "scenario calculation never touches production data" requirement
    reduces to at the domain level — see the regression test in
    tests/domain/test_scenario.py and the end-to-end version in
    tests/api/test_scenarios.py.

    Assumes operations already passed service-layer validation (references
    resolve, hours are non-negative, move/adjust targets exist) — same
    convention as app/domain/capacity.py's defensive-fallback comments.
    Raises ValueError (not a DomainError — this module has no framework
    dependency) if an operation is structurally impossible against the
    state at its point in the sequence, so a validation gap fails loudly
    instead of silently producing a wrong number.
    """
    state = baseline
    for operation in sorted(operations, key=lambda op: op.sequence):
        state = _apply_one(state, operation)
    return state

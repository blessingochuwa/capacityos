"""Pure tests of the scenario transformation layer — no database, no
FastAPI (same discipline as tests/domain/test_capacity.py).

Anchor date: 2026-08-17 is a Monday.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.domain.capacity import AvailabilityExceptionFact, ScheduleFact
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

MONDAY = date(2026, 8, 17)
FRIDAY = date(2026, 8, 21)  # 5 weekdays — chosen so hours_per_week/5 and
SUNDAY = date(2026, 8, 23)  # allocation_hours/days_in_range divide evenly,
# same reason ADR 0003 documents allocation_amount_for_date rounding
# artifacts on ranges that don't divide evenly — these tests are about
# scenario mechanics, not Phase 2 rounding (already covered by
# tests/domain/test_capacity.py), so ranges here are chosen to avoid it.
MON_FRI_8H = {weekday: Decimal("8") for weekday in range(5)}

PERSON_A = uuid.UUID(int=1)
PERSON_B = uuid.UUID(int=2)
PROJECT_X = uuid.UUID(int=100)
PROJECT_Y = uuid.UUID(int=101)
ALLOCATION_1 = uuid.UUID(int=1000)


def _schedule() -> ScheduleFact:
    from datetime import UTC, datetime

    return ScheduleFact(
        effective_start_date=None,
        effective_end_date=None,
        entries=MON_FRI_8H,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _state(
    *,
    allocations: tuple[IdentifiedAllocationFact, ...] = (),
    person_ids: tuple[uuid.UUID, ...] = (),
) -> PlanningState:
    schedules = {person_id: (_schedule(),) for person_id in person_ids}
    return PlanningState(schedules=schedules, allocations=allocations)


def _op_id(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


# ---------------------------------------------------------------------------
# Empty scenario / baseline immutability
# ---------------------------------------------------------------------------


def test_empty_scenario_returns_equivalent_state() -> None:
    baseline = _state(person_ids=(PERSON_A,))
    result = apply_scenario_operations(baseline, [])
    assert result == baseline


def test_apply_never_mutates_baseline_object() -> None:
    allocation = IdentifiedAllocationFact(
        id=ALLOCATION_1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        start_date=MONDAY,
        end_date=SUNDAY,
        allocation_hours=Decimal("20"),
    )
    baseline = _state(allocations=(allocation,), person_ids=(PERSON_A, PERSON_B))

    apply_scenario_operations(
        baseline,
        [
            AddAllocationOperation(
                id=_op_id(1),
                sequence=0,
                person_id=PERSON_B,
                project_id=PROJECT_X,
                hours=Decimal("10"),
                start_date=MONDAY,
                end_date=SUNDAY,
            ),
            RemoveAllocationOperation(id=_op_id(2), sequence=1, allocation_id=ALLOCATION_1),
        ],
    )

    # Baseline is exactly as it was before apply_scenario_operations ran —
    # this is the domain-level half of "scenario calculation never mutates
    # production data" (see tests/api/test_scenarios.py for the end-to-end half).
    assert baseline.allocations == (allocation,)
    assert PERSON_A in baseline.schedules
    assert PERSON_B in baseline.schedules


def test_determinism_same_input_twice_equal_output() -> None:
    baseline = _state(person_ids=(PERSON_A,))
    ops = [
        AddAllocationOperation(
            id=_op_id(1),
            sequence=0,
            person_id=PERSON_A,
            project_id=PROJECT_X,
            hours=Decimal("12"),
            start_date=MONDAY,
            end_date=SUNDAY,
        )
    ]
    first = apply_scenario_operations(baseline, ops)
    second = apply_scenario_operations(baseline, ops)
    assert first == second


# ---------------------------------------------------------------------------
# Individual operation types
# ---------------------------------------------------------------------------


def test_add_allocation() -> None:
    baseline = _state(person_ids=(PERSON_A,))
    result = apply_scenario_operations(
        baseline,
        [
            AddAllocationOperation(
                id=_op_id(1),
                sequence=0,
                person_id=PERSON_A,
                project_id=PROJECT_X,
                hours=Decimal("16"),
                start_date=MONDAY,
                end_date=MONDAY,
            )
        ],
    )
    capacity = person_capacity_from_state(result, PERSON_A, MONDAY, MONDAY)
    assert capacity.allocated_hours == Decimal("16.00")


def test_adjust_allocation_changes_hours() -> None:
    allocation = IdentifiedAllocationFact(
        id=ALLOCATION_1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        start_date=MONDAY,
        end_date=MONDAY,
        allocation_hours=Decimal("20"),
    )
    baseline = _state(allocations=(allocation,), person_ids=(PERSON_A,))
    result = apply_scenario_operations(
        baseline,
        [
            AdjustAllocationOperation(
                id=_op_id(1),
                sequence=0,
                allocation_id=ALLOCATION_1,
                hours=Decimal("30"),
                start_date=None,
                end_date=None,
            )
        ],
    )
    capacity = person_capacity_from_state(result, PERSON_A, MONDAY, MONDAY)
    assert capacity.allocated_hours == Decimal("30.00")


def test_remove_allocation() -> None:
    allocation = IdentifiedAllocationFact(
        id=ALLOCATION_1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        start_date=MONDAY,
        end_date=SUNDAY,
        allocation_hours=Decimal("20"),
    )
    baseline = _state(allocations=(allocation,), person_ids=(PERSON_A,))
    result = apply_scenario_operations(
        baseline,
        [RemoveAllocationOperation(id=_op_id(1), sequence=0, allocation_id=ALLOCATION_1)],
    )
    capacity = person_capacity_from_state(result, PERSON_A, MONDAY, SUNDAY)
    assert capacity.allocated_hours == Decimal("0.00")


def test_move_allocation_full() -> None:
    allocation = IdentifiedAllocationFact(
        id=ALLOCATION_1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        start_date=MONDAY,
        end_date=MONDAY,
        allocation_hours=Decimal("20"),
    )
    baseline = _state(allocations=(allocation,), person_ids=(PERSON_A, PERSON_B))
    result = apply_scenario_operations(
        baseline,
        [
            MoveAllocationOperation(
                id=_op_id(1),
                sequence=0,
                allocation_id=ALLOCATION_1,
                to_person_id=PERSON_B,
                hours=None,
            )
        ],
    )
    assert person_capacity_from_state(result, PERSON_A, MONDAY, MONDAY).allocated_hours == Decimal(
        "0.00"
    )
    assert person_capacity_from_state(result, PERSON_B, MONDAY, MONDAY).allocated_hours == Decimal(
        "20.00"
    )


def test_move_allocation_partial_splits() -> None:
    allocation = IdentifiedAllocationFact(
        id=ALLOCATION_1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        start_date=MONDAY,
        end_date=MONDAY,
        allocation_hours=Decimal("20"),
    )
    baseline = _state(allocations=(allocation,), person_ids=(PERSON_A, PERSON_B))
    result = apply_scenario_operations(
        baseline,
        [
            MoveAllocationOperation(
                id=_op_id(1),
                sequence=0,
                allocation_id=ALLOCATION_1,
                to_person_id=PERSON_B,
                hours=Decimal("8"),
            )
        ],
    )
    assert person_capacity_from_state(result, PERSON_A, MONDAY, MONDAY).allocated_hours == Decimal(
        "12.00"
    )
    assert person_capacity_from_state(result, PERSON_B, MONDAY, MONDAY).allocated_hours == Decimal(
        "8.00"
    )


def test_shift_project_moves_dates() -> None:
    allocation = IdentifiedAllocationFact(
        id=ALLOCATION_1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        start_date=MONDAY,
        end_date=SUNDAY,
        allocation_hours=Decimal("14"),
    )
    baseline = _state(allocations=(allocation,), person_ids=(PERSON_A,))
    result = apply_scenario_operations(
        baseline,
        [ShiftProjectOperation(id=_op_id(1), sequence=0, project_id=PROJECT_X, day_offset=-7)],
    )
    shifted = next(a for a in result.allocations if a.id == ALLOCATION_1)
    assert shifted.start_date == date(2026, 8, 10)
    assert shifted.end_date == date(2026, 8, 16)


def test_shift_project_only_affects_that_project() -> None:
    allocation_x = IdentifiedAllocationFact(
        id=ALLOCATION_1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        start_date=MONDAY,
        end_date=SUNDAY,
        allocation_hours=Decimal("10"),
    )
    allocation_y = IdentifiedAllocationFact(
        id=uuid.UUID(int=1001),
        person_id=PERSON_A,
        project_id=PROJECT_Y,
        start_date=MONDAY,
        end_date=SUNDAY,
        allocation_hours=Decimal("10"),
    )
    baseline = _state(allocations=(allocation_x, allocation_y), person_ids=(PERSON_A,))
    result = apply_scenario_operations(
        baseline,
        [ShiftProjectOperation(id=_op_id(1), sequence=0, project_id=PROJECT_X, day_offset=7)],
    )
    untouched = next(a for a in result.allocations if a.project_id == PROJECT_Y)
    assert untouched.start_date == MONDAY


def test_availability_override_fully_unavailable() -> None:
    allocation = IdentifiedAllocationFact(
        id=ALLOCATION_1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        start_date=MONDAY,
        end_date=MONDAY,
        allocation_hours=Decimal("8"),
    )
    baseline = _state(allocations=(allocation,), person_ids=(PERSON_A,))
    result = apply_scenario_operations(
        baseline,
        [
            AvailabilityOverrideOperation(
                id=_op_id(1),
                sequence=0,
                person_id=PERSON_A,
                start_date=MONDAY,
                end_date=MONDAY,
                hours=None,
            )
        ],
    )
    capacity = person_capacity_from_state(result, PERSON_A, MONDAY, MONDAY)
    assert capacity.effective_capacity == Decimal("0.00")
    assert capacity.over_allocation == Decimal("8.00")


def test_availability_clear_restores_normal_schedule() -> None:
    full_week_leave = AvailabilityExceptionFact(start_date=MONDAY, end_date=SUNDAY, hours=None)
    baseline = PlanningState(
        schedules={PERSON_A: (_schedule(),)},
        exceptions={PERSON_A: (full_week_leave,)},
    )
    result = apply_scenario_operations(
        baseline,
        [
            AvailabilityClearOperation(
                id=_op_id(1), sequence=0, person_id=PERSON_A, start_date=MONDAY, end_date=SUNDAY
            )
        ],
    )
    capacity = person_capacity_from_state(result, PERSON_A, MONDAY, SUNDAY)
    assert capacity.effective_capacity == Decimal("40.00")  # Mon-Fri 8h, exception cleared


def test_availability_clear_partial_overlap_keeps_remainder() -> None:
    tuesday = date(2026, 8, 18)
    full_week_leave = AvailabilityExceptionFact(start_date=MONDAY, end_date=SUNDAY, hours=None)
    baseline = PlanningState(
        schedules={PERSON_A: (_schedule(),)},
        exceptions={PERSON_A: (full_week_leave,)},
    )
    result = apply_scenario_operations(
        baseline,
        [
            AvailabilityClearOperation(
                id=_op_id(1), sequence=0, person_id=PERSON_A, start_date=MONDAY, end_date=tuesday
            )
        ],
    )
    remaining = result.exceptions[PERSON_A]
    assert remaining == (
        AvailabilityExceptionFact(start_date=date(2026, 8, 19), end_date=SUNDAY, hours=None),
    )


def test_add_hypothetical_resource_then_allocate() -> None:
    baseline = _state()
    hypothetical_id = _op_id(1)
    result = apply_scenario_operations(
        baseline,
        [
            AddHypotheticalResourceOperation(
                id=hypothetical_id,
                sequence=0,
                label="Senior Designer",
                hours_per_week=Decimal("40"),
                start_date=MONDAY,
                end_date=FRIDAY,
            ),
            AddAllocationOperation(
                id=_op_id(2),
                sequence=1,
                person_id=hypothetical_id,
                project_id=PROJECT_X,
                hours=Decimal("20"),
                start_date=MONDAY,
                end_date=FRIDAY,
            ),
        ],
    )
    capacity = person_capacity_from_state(result, hypothetical_id, MONDAY, FRIDAY)
    assert capacity.effective_capacity == Decimal("40.00")
    assert capacity.allocated_hours == Decimal("20.00")
    assert capacity.remaining_capacity == Decimal("20.00")


# ---------------------------------------------------------------------------
# Composed / multiple operations, order-dependence
# ---------------------------------------------------------------------------


def test_multiple_operations_compose() -> None:
    allocation = IdentifiedAllocationFact(
        id=ALLOCATION_1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        start_date=MONDAY,
        end_date=MONDAY,
        allocation_hours=Decimal("10"),
    )
    baseline = _state(allocations=(allocation,), person_ids=(PERSON_A, PERSON_B))
    result = apply_scenario_operations(
        baseline,
        [
            AddAllocationOperation(
                id=_op_id(1),
                sequence=0,
                person_id=PERSON_B,
                project_id=PROJECT_X,
                hours=Decimal("5"),
                start_date=MONDAY,
                end_date=MONDAY,
            ),
            AdjustAllocationOperation(
                id=_op_id(2),
                sequence=1,
                allocation_id=ALLOCATION_1,
                hours=Decimal("15"),
                start_date=None,
                end_date=None,
            ),
        ],
    )
    demand = project_demand_from_state(result, PROJECT_X, MONDAY, MONDAY)
    assert demand.allocated_hours == Decimal("20.00")  # 15 (adjusted) + 5 (added)


def test_operations_apply_in_sequence_order_not_list_order() -> None:
    """shift_project only shifts allocations that exist in the working set at
    that point in the SEQUENCE — an add_allocation with a lower sequence
    number is shifted even if it appears later in the input list."""
    baseline = _state(person_ids=(PERSON_A,))
    add_op = AddAllocationOperation(
        id=_op_id(1),
        sequence=0,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        hours=Decimal("10"),
        start_date=MONDAY,
        end_date=SUNDAY,
    )
    shift_op = ShiftProjectOperation(id=_op_id(2), sequence=1, project_id=PROJECT_X, day_offset=7)

    # Pass them in reverse list order — apply_scenario_operations must sort by `sequence`.
    result = apply_scenario_operations(baseline, [shift_op, add_op])
    shifted = next(a for a in result.allocations if a.id == _op_id(1))
    assert shifted.start_date == date(2026, 8, 24)


def test_shift_project_before_allocation_added_leaves_it_unshifted() -> None:
    baseline = _state(person_ids=(PERSON_A,))
    shift_op = ShiftProjectOperation(id=_op_id(1), sequence=0, project_id=PROJECT_X, day_offset=7)
    add_op = AddAllocationOperation(
        id=_op_id(2),
        sequence=1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        hours=Decimal("10"),
        start_date=MONDAY,
        end_date=SUNDAY,
    )
    result = apply_scenario_operations(baseline, [shift_op, add_op])
    unshifted = next(a for a in result.allocations if a.id == _op_id(2))
    assert unshifted.start_date == MONDAY


# ---------------------------------------------------------------------------
# Structurally invalid operations (service layer should never let these
# through, but the domain layer fails loudly rather than silently, per its
# module docstring)
# ---------------------------------------------------------------------------


def test_adjust_unknown_allocation_raises() -> None:
    baseline = _state(person_ids=(PERSON_A,))
    with pytest.raises(ValueError, match="unknown allocation_id"):
        apply_scenario_operations(
            baseline,
            [
                AdjustAllocationOperation(
                    id=_op_id(1),
                    sequence=0,
                    allocation_id=uuid.UUID(int=9999),
                    hours=Decimal("5"),
                    start_date=None,
                    end_date=None,
                )
            ],
        )


def test_move_more_hours_than_exist_raises() -> None:
    allocation = IdentifiedAllocationFact(
        id=ALLOCATION_1,
        person_id=PERSON_A,
        project_id=PROJECT_X,
        start_date=MONDAY,
        end_date=SUNDAY,
        allocation_hours=Decimal("10"),
    )
    baseline = _state(allocations=(allocation,), person_ids=(PERSON_A, PERSON_B))
    with pytest.raises(ValueError, match="cannot move"):
        apply_scenario_operations(
            baseline,
            [
                MoveAllocationOperation(
                    id=_op_id(1),
                    sequence=0,
                    allocation_id=ALLOCATION_1,
                    to_person_id=PERSON_B,
                    hours=Decimal("99"),
                )
            ],
        )

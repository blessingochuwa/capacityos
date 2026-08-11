"""Pure tests of the capacity engine — no database, no FastAPI (CLAUDE.md
§10/§22: the calculation layer must be testable without either).

Anchor date: 2026-08-17 is a Monday (matches the task spec's own examples).
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.capacity import (
    AllocationFact,
    AvailabilityExceptionFact,
    ProjectAllocationFact,
    ScheduleFact,
    aggregate_team_capacity,
    calculate_daily_capacity,
    calculate_period_capacity,
    calculate_project_demand,
)

MONDAY = date(2026, 8, 17)
TUESDAY = date(2026, 8, 18)
SATURDAY = date(2026, 8, 22)
SUNDAY = date(2026, 8, 23)

MON_FRI_8H = {weekday: Decimal("8") for weekday in range(5)}  # Mon-Fri 8h; Sat/Sun unset (0)


def _schedule(
    entries: dict[int, Decimal] | None = None,
    *,
    effective_start_date: date | None = None,
    effective_end_date: date | None = None,
    created_at: datetime = datetime(2026, 1, 1, tzinfo=UTC),
) -> ScheduleFact:
    return ScheduleFact(
        effective_start_date=effective_start_date,
        effective_end_date=effective_end_date,
        entries=MON_FRI_8H if entries is None else entries,
        created_at=created_at,
    )


def _exception(start: date, end: date, hours: Decimal | None = None) -> AvailabilityExceptionFact:
    return AvailabilityExceptionFact(start_date=start, end_date=end, hours=hours)


def _allocation(start: date, end: date, hours: Decimal) -> AllocationFact:
    return AllocationFact(start_date=start, end_date=end, allocation_hours=hours)


# ---------------------------------------------------------------------------
# Spec §25 matrix
# ---------------------------------------------------------------------------


def test_basic_capacity_no_exceptions_no_allocations() -> None:
    day = calculate_daily_capacity(MONDAY, [_schedule()], [], [])
    assert day.scheduled_hours == Decimal("8")
    assert day.unavailable_hours == Decimal("0")
    assert day.effective_capacity == Decimal("8")
    assert day.allocated_hours == Decimal("0")
    assert day.remaining_capacity == Decimal("8")
    assert day.utilization == Decimal("0.0000")
    assert day.over_allocation == Decimal("0")


def test_normal_allocation() -> None:
    allocations = [_allocation(MONDAY, MONDAY, Decimal("4"))]
    day = calculate_daily_capacity(MONDAY, [_schedule()], [], allocations)
    assert day.remaining_capacity == Decimal("4")
    assert day.utilization == Decimal("0.5000")
    assert day.over_allocation == Decimal("0")


def test_full_allocation() -> None:
    allocations = [_allocation(MONDAY, MONDAY, Decimal("8"))]
    day = calculate_daily_capacity(MONDAY, [_schedule()], [], allocations)
    assert day.remaining_capacity == Decimal("0")
    assert day.utilization == Decimal("1.0000")
    assert day.over_allocation == Decimal("0")


def test_over_allocation() -> None:
    allocations = [_allocation(MONDAY, MONDAY, Decimal("10"))]
    day = calculate_daily_capacity(MONDAY, [_schedule()], [], allocations)
    assert day.remaining_capacity == Decimal("-2")
    assert day.utilization == Decimal("1.2500")
    assert day.over_allocation == Decimal("2")


def test_full_leave() -> None:
    exceptions = [_exception(MONDAY, MONDAY, hours=None)]
    day = calculate_daily_capacity(MONDAY, [_schedule()], exceptions, [])
    assert day.effective_capacity == Decimal("0")
    assert day.remaining_capacity == Decimal("0")
    assert day.utilization is None
    assert day.over_allocation == Decimal("0")


def test_leave_with_allocation_conflict() -> None:
    """A person on full leave but with 8h allocated: a genuine capacity
    conflict, not simply '8 hours allocated' — surfaced via over_allocation/
    remaining_capacity, not a misleading numeric utilization."""
    exceptions = [_exception(MONDAY, MONDAY, hours=None)]
    allocations = [_allocation(MONDAY, MONDAY, Decimal("8"))]
    day = calculate_daily_capacity(MONDAY, [_schedule()], exceptions, allocations)
    assert day.effective_capacity == Decimal("0")
    assert day.remaining_capacity == Decimal("-8")
    assert day.over_allocation == Decimal("8")
    assert day.utilization is None


def test_partial_availability() -> None:
    exceptions = [_exception(MONDAY, MONDAY, hours=Decimal("4"))]
    day = calculate_daily_capacity(MONDAY, [_schedule()], exceptions, [])
    assert day.effective_capacity == Decimal("4")
    assert day.unavailable_hours == Decimal("4")


def test_weekend_allocation_is_a_conflict_not_silently_moved() -> None:
    """Schedule has no Saturday hours; an allocation placed on a Saturday
    must surface as over-allocation, not be redistributed to a working day."""
    allocations = [_allocation(SATURDAY, SATURDAY, Decimal("5"))]
    day = calculate_daily_capacity(SATURDAY, [_schedule()], [], allocations)
    assert day.scheduled_hours == Decimal("0")
    assert day.effective_capacity == Decimal("0")
    assert day.allocated_hours == Decimal("5")
    assert day.remaining_capacity == Decimal("-5")
    assert day.over_allocation == Decimal("5")


def test_multiple_projects_over_allocate_a_week() -> None:
    """Spec §25 example: 40h effective; A=20h, B=15h, C=10h -> 45 allocated,
    -5 remaining, 112.5% utilization, 5 over-allocation."""
    week_end = date(2026, 8, 21)  # Friday of the same week as MONDAY
    allocations = [
        _allocation(MONDAY, week_end, Decimal("20")),
        _allocation(MONDAY, week_end, Decimal("15")),
        _allocation(MONDAY, week_end, Decimal("10")),
    ]
    result = calculate_period_capacity(MONDAY, week_end, [_schedule()], [], allocations)
    assert result.gross_capacity == Decimal("40")
    assert result.effective_capacity == Decimal("40")
    assert result.allocated_hours == Decimal("45")
    assert result.remaining_capacity == Decimal("-5")
    assert result.utilization == Decimal("1.1250")
    assert result.over_allocation == Decimal("5")


def test_overlapping_availability_exceptions_use_most_restrictive() -> None:
    """Exception A leaves 4h available, exception B leaves 2h available on
    the same day. The result must be min(4, 2) = 2 — never a naive sum
    (4 + 2 = 6 would imply MORE availability than either exception alone,
    which is nonsensical)."""
    exceptions = [
        _exception(MONDAY, MONDAY, hours=Decimal("4")),
        _exception(MONDAY, MONDAY, hours=Decimal("2")),
    ]
    day = calculate_daily_capacity(MONDAY, [_schedule()], exceptions, [])
    assert day.effective_capacity == Decimal("2")
    assert day.effective_capacity != Decimal("6")


def test_overlapping_full_and_partial_exception_full_wins() -> None:
    exceptions = [
        _exception(MONDAY, MONDAY, hours=None),
        _exception(MONDAY, MONDAY, hours=Decimal("4")),
    ]
    day = calculate_daily_capacity(MONDAY, [_schedule()], exceptions, [])
    assert day.effective_capacity == Decimal("0")


def test_team_utilization_is_weighted_not_averaged() -> None:
    """Spec §18: Person A effective=40/allocated=40 (100%), Person B
    effective=10/allocated=5 (50%). Team utilization must be 45/50 = 90%,
    not the naive average of 75%."""
    person_a = calculate_period_capacity(
        MONDAY,
        MONDAY,
        [_schedule({0: Decimal("40")})],
        [],
        [_allocation(MONDAY, MONDAY, Decimal("40"))],
    )
    person_b = calculate_period_capacity(
        MONDAY,
        MONDAY,
        [_schedule({0: Decimal("10")})],
        [],
        [_allocation(MONDAY, MONDAY, Decimal("5"))],
    )
    team = aggregate_team_capacity(MONDAY, MONDAY, [person_a, person_b])
    assert team.effective_capacity == Decimal("50")
    assert team.allocated_hours == Decimal("45")
    assert team.utilization == Decimal("0.9000")
    assert team.utilization != Decimal("0.7500")


def test_team_totals_equal_sum_of_member_totals() -> None:
    person_a = calculate_period_capacity(
        MONDAY, TUESDAY, [_schedule()], [], [_allocation(MONDAY, TUESDAY, Decimal("10"))]
    )
    person_b = calculate_period_capacity(
        MONDAY, TUESDAY, [_schedule()], [], [_allocation(MONDAY, TUESDAY, Decimal("6"))]
    )
    team = aggregate_team_capacity(MONDAY, TUESDAY, [person_a, person_b])
    assert team.effective_capacity == person_a.effective_capacity + person_b.effective_capacity
    assert team.allocated_hours == person_a.allocated_hours + person_b.allocated_hours
    assert team.remaining_capacity == person_a.remaining_capacity + person_b.remaining_capacity


def test_empty_team_returns_well_formed_zero_result() -> None:
    team = aggregate_team_capacity(MONDAY, SUNDAY, [])
    assert team.effective_capacity == Decimal("0")
    assert team.allocated_hours == Decimal("0")
    assert team.utilization is None
    assert team.over_allocation == Decimal("0")


# ---------------------------------------------------------------------------
# Working schedule selection
# ---------------------------------------------------------------------------


def test_no_matching_schedule_means_zero_scheduled_hours() -> None:
    schedule = _schedule(effective_start_date=date(2027, 1, 1))  # not effective yet
    day = calculate_daily_capacity(MONDAY, [schedule], [], [])
    assert day.scheduled_hours == Decimal("0")
    assert day.effective_capacity == Decimal("0")


def test_multiple_matching_schedules_falls_back_to_most_recently_created() -> None:
    """Defensive-only path: WorkingScheduleService rejects overlapping
    schedules at write time, so this should be unreachable via the API, but
    the engine must still be deterministic if it's ever hit (e.g. legacy
    data)."""
    older = _schedule({0: Decimal("8")}, created_at=datetime(2026, 1, 1, tzinfo=UTC))
    newer = _schedule({0: Decimal("6")}, created_at=datetime(2026, 6, 1, tzinfo=UTC))
    day = calculate_daily_capacity(MONDAY, [older, newer], [], [])
    assert day.scheduled_hours == Decimal("6")


# ---------------------------------------------------------------------------
# Allocation windows relative to the requested period
# ---------------------------------------------------------------------------


def test_allocation_entirely_outside_requested_period_contributes_nothing() -> None:
    allocations = [_allocation(date(2026, 9, 1), date(2026, 9, 5), Decimal("20"))]
    result = calculate_period_capacity(MONDAY, TUESDAY, [_schedule()], [], allocations)
    assert result.allocated_hours == Decimal("0")


def test_allocation_spanning_beyond_requested_period_uses_its_own_full_span() -> None:
    """A 21-day, 21-hour allocation (1h/day) queried over a 5-day sub-window
    inside it must show 5 allocated hours, not the full 21 or a re-derived
    rate based on the query window."""
    allocations = [_allocation(date(2026, 8, 10), date(2026, 8, 30), Decimal("21"))]
    result = calculate_period_capacity(MONDAY, date(2026, 8, 21), [_schedule()], [], allocations)
    assert result.allocated_hours == Decimal("5.00")


def test_multiple_overlapping_allocations_for_different_projects_sum() -> None:
    """Cross-project contention (spec §20): overlapping allocations for
    different projects add up, they don't error or overwrite each other."""
    allocations = [
        _allocation(MONDAY, MONDAY, Decimal("3")),
        _allocation(MONDAY, MONDAY, Decimal("2")),
    ]
    day = calculate_daily_capacity(MONDAY, [_schedule()], [], allocations)
    assert day.allocated_hours == Decimal("5")


# ---------------------------------------------------------------------------
# Invariants (spec §26)
# ---------------------------------------------------------------------------


def test_effective_capacity_never_exceeds_gross_capacity() -> None:
    exceptions = [_exception(MONDAY, MONDAY, hours=Decimal("100"))]  # absurdly generous exception
    day = calculate_daily_capacity(MONDAY, [_schedule()], exceptions, [])
    assert day.effective_capacity <= day.scheduled_hours


def test_over_allocation_is_never_negative() -> None:
    allocations = [_allocation(MONDAY, MONDAY, Decimal("1"))]
    day = calculate_daily_capacity(MONDAY, [_schedule()], [], allocations)
    assert day.over_allocation >= Decimal("0")


def test_remaining_capacity_equals_effective_minus_allocated() -> None:
    allocations = [_allocation(MONDAY, MONDAY, Decimal("3"))]
    day = calculate_daily_capacity(MONDAY, [_schedule()], [], allocations)
    assert day.remaining_capacity == day.effective_capacity - day.allocated_hours


def test_calculation_does_not_mutate_inputs() -> None:
    schedules = [_schedule()]
    exceptions = [_exception(MONDAY, MONDAY, hours=Decimal("4"))]
    allocations = [_allocation(MONDAY, MONDAY, Decimal("2"))]
    snapshot = (list(schedules), list(exceptions), list(allocations))

    calculate_period_capacity(MONDAY, SUNDAY, schedules, exceptions, allocations)

    assert (schedules, exceptions, allocations) == snapshot


def test_calculation_is_idempotent() -> None:
    schedules = [_schedule()]
    exceptions = [_exception(MONDAY, MONDAY, hours=Decimal("4"))]
    allocations = [_allocation(MONDAY, MONDAY, Decimal("2"))]

    first = calculate_period_capacity(MONDAY, SUNDAY, schedules, exceptions, allocations)
    second = calculate_period_capacity(MONDAY, SUNDAY, schedules, exceptions, allocations)

    assert first == second


# ---------------------------------------------------------------------------
# Project demand
# ---------------------------------------------------------------------------


def test_project_demand_totals_and_by_person_breakdown() -> None:
    alice = uuid.uuid4()
    bob = uuid.uuid4()
    facts = [
        ProjectAllocationFact(
            person_id=alice, allocation=_allocation(MONDAY, TUESDAY, Decimal("10"))
        ),
        ProjectAllocationFact(person_id=bob, allocation=_allocation(MONDAY, MONDAY, Decimal("4"))),
    ]
    result = calculate_project_demand(MONDAY, TUESDAY, facts)

    assert result.allocated_hours == Decimal("14")
    assert result.allocated_people == 2
    by_person = {entry.person_id: entry.allocated_hours for entry in result.by_person}
    assert by_person[alice] == Decimal("10")
    assert by_person[bob] == Decimal("4")

    monday_total = next(day.allocated_hours for day in result.daily_breakdown if day.date == MONDAY)
    assert monday_total == Decimal("9")  # alice 5.00 (10/2) + bob 4.00


def test_project_demand_excludes_people_with_no_hours_in_range() -> None:
    alice = uuid.uuid4()
    facts = [
        ProjectAllocationFact(
            person_id=alice,
            allocation=_allocation(date(2026, 9, 1), date(2026, 9, 5), Decimal("20")),
        )
    ]
    result = calculate_project_demand(MONDAY, TUESDAY, facts)
    assert result.allocated_hours == Decimal("0")
    assert result.allocated_people == 0
    assert result.by_person == ()

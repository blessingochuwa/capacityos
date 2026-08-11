"""The deterministic capacity engine (CLAUDE.md §10, §39 Phase 2).

Pure, side-effect-free calculations over plain data — no SQLAlchemy, no I/O,
no framework imports. Same inputs always produce the same outputs, and
nothing here mutates its arguments. The service layer (app/services/capacity.py)
is responsible for turning ORM rows into the *Fact dataclasses below and for
attaching identifiers (person_id, team_id, ...) to the results.

See docs/domain-concepts.md ("Capacity Engine" section) and
docs/adr/0003-phase-2-capacity-engine.md for the formulas and the reasoning
behind the design decisions encoded here (allocation time-phasing, overlapping
availability exceptions, zero-capacity utilization, team weighting).
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.domain.dates import iterate_dates

ZERO = Decimal("0.00")
"""Quantized to 2 decimal places (see HOURS_QUANTUM) so that min()/max()/sum()
involving this constant never silently drop back to a bare-integer Decimal
exponent in the output — Decimal's arithmetic methods return whichever
operand's own representation applies, so an unquantized zero would make
values like over_allocation serialize as "0" on some inputs and "0.00" on
others despite being numerically identical."""
HOURS_QUANTUM = Decimal("0.01")
"""Matches the Numeric(4,2)/Numeric(6,2) precision already used for hour
columns in Phase 1 (WorkingScheduleEntry.hours, AvailabilityException.hours,
Allocation.allocation_hours) — this is not an arbitrary choice."""
UTILIZATION_QUANTUM = Decimal("0.0001")


def _quantize_hours(value: Decimal) -> Decimal:
    return value.quantize(HOURS_QUANTUM, rounding=ROUND_HALF_UP)


def _quantize_utilization(value: Decimal) -> Decimal:
    return value.quantize(UTILIZATION_QUANTUM, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Input facts — built by the service layer from ORM rows
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScheduleFact:
    """One WorkingSchedule's shape, stripped of identifiers.

    entries maps date.weekday() (0=Monday..6=Sunday) to scheduled hours.
    created_at exists only for the defensive tie-break in
    _scheduled_hours_for_date — see that function's docstring.
    """

    effective_start_date: date | None
    effective_end_date: date | None
    entries: Mapping[int, Decimal]
    created_at: datetime


@dataclass(frozen=True)
class AvailabilityExceptionFact:
    """hours=None means fully unavailable for [start_date, end_date]; a value
    means available that many hours PER DAY during the period — see
    app/models/availability_exception.py."""

    start_date: date
    end_date: date
    hours: Decimal | None


@dataclass(frozen=True)
class AllocationFact:
    """allocation_hours is the TOTAL over [start_date, end_date], time-phased
    evenly across every calendar day in that range — see
    docs/adr/0003-phase-2-capacity-engine.md decision #1."""

    start_date: date
    end_date: date
    allocation_hours: Decimal


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyCapacity:
    date: date
    scheduled_hours: Decimal
    unavailable_hours: Decimal
    effective_capacity: Decimal
    allocated_hours: Decimal
    remaining_capacity: Decimal
    utilization: Decimal | None
    over_allocation: Decimal


@dataclass(frozen=True)
class PersonCapacityResult:
    start_date: date
    end_date: date
    gross_capacity: Decimal
    unavailable_hours: Decimal
    effective_capacity: Decimal
    allocated_hours: Decimal
    remaining_capacity: Decimal
    utilization: Decimal | None
    over_allocation: Decimal
    daily_breakdown: tuple[DailyCapacity, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TeamCapacityResult:
    start_date: date
    end_date: date
    gross_capacity: Decimal
    unavailable_hours: Decimal
    effective_capacity: Decimal
    allocated_hours: Decimal
    remaining_capacity: Decimal
    utilization: Decimal | None
    over_allocation: Decimal


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------


def _scheduled_hours_for_date(schedules: Sequence[ScheduleFact], target_date: date) -> Decimal:
    """The person's normal scheduled hours for target_date, from whichever
    WorkingSchedule is effective on that date.

    WorkingScheduleService rejects overlapping effective ranges for the same
    person at write time (docs/adr/0003-phase-2-capacity-engine.md decision
    #3), so `matching` should never have more than one entry in practice. If
    it ever does (e.g. data written before that validation existed), the most
    recently created schedule wins — a deterministic fallback rather than a
    raised error, so the engine still returns an answer for pre-existing data.
    Zero matching schedules means the person has no normal working pattern on
    that date, i.e. 0 scheduled hours (not an error).
    """
    matching = [
        schedule
        for schedule in schedules
        if (schedule.effective_start_date is None or schedule.effective_start_date <= target_date)
        and (schedule.effective_end_date is None or schedule.effective_end_date >= target_date)
    ]
    if not matching:
        return ZERO
    schedule = max(matching, key=lambda s: s.created_at)
    return schedule.entries.get(target_date.weekday(), ZERO)


def _effective_capacity_for_date(
    scheduled_hours: Decimal,
    exceptions: Sequence[AvailabilityExceptionFact],
    target_date: date,
) -> Decimal:
    """Apply every AvailabilityException covering target_date, most-restrictive-wins.

    Each covering exception contributes an "available that day" value (0 if
    hours is None, else hours). Effective capacity is the minimum of the
    normal scheduled hours and all of those values — never higher than the
    schedule, and never a naive sum of multiple exceptions (see decision #2).
    """
    available_values = [
        ZERO if exception.hours is None else exception.hours
        for exception in exceptions
        if exception.start_date <= target_date <= exception.end_date
    ]
    if not available_values:
        return scheduled_hours
    return min(scheduled_hours, *available_values)


def allocation_amount_for_date(allocation: AllocationFact, target_date: date) -> Decimal:
    """This allocation's contribution to target_date: its total hours spread
    evenly across every calendar day in [start_date, end_date] (decision #1).
    Zero if target_date falls outside the allocation's range.

    Public (not person-capacity-specific) because project demand
    (CapacityService.get_project_demand) time-phases allocations the same
    way, without needing a person's schedule/effective-capacity at all.
    """
    if not (allocation.start_date <= target_date <= allocation.end_date):
        return ZERO
    total_days = (allocation.end_date - allocation.start_date).days + 1
    return _quantize_hours(allocation.allocation_hours / total_days)


def calculate_daily_capacity(
    target_date: date,
    schedules: Sequence[ScheduleFact],
    exceptions: Sequence[AvailabilityExceptionFact],
    allocations: Sequence[AllocationFact],
) -> DailyCapacity:
    """One day's full capacity picture, explainable end to end.

    allocated_hours sums every allocation's time-phased contribution for this
    date — including allocations on days the person isn't scheduled to work
    at all (e.g. a weekend), which surfaces as a real conflict via
    over_allocation/remaining_capacity rather than being silently absorbed.
    """
    scheduled_hours = _scheduled_hours_for_date(schedules, target_date)
    effective_capacity = _effective_capacity_for_date(scheduled_hours, exceptions, target_date)
    unavailable_hours = scheduled_hours - effective_capacity
    allocated_hours = sum(
        (allocation_amount_for_date(allocation, target_date) for allocation in allocations), ZERO
    )
    remaining_capacity = effective_capacity - allocated_hours
    over_allocation = max(allocated_hours - effective_capacity, ZERO)
    utilization = (
        _quantize_utilization(allocated_hours / effective_capacity)
        if effective_capacity > ZERO
        else None
    )
    return DailyCapacity(
        date=target_date,
        scheduled_hours=scheduled_hours,
        unavailable_hours=unavailable_hours,
        effective_capacity=effective_capacity,
        allocated_hours=allocated_hours,
        remaining_capacity=remaining_capacity,
        utilization=utilization,
        over_allocation=over_allocation,
    )


def calculate_period_capacity(
    start_date: date,
    end_date: date,
    schedules: Sequence[ScheduleFact],
    exceptions: Sequence[AvailabilityExceptionFact],
    allocations: Sequence[AllocationFact],
) -> PersonCapacityResult:
    """A person's capacity over [start_date, end_date] — day, week, or any
    arbitrary range are all just this same function with different bounds
    (spec §4/§11: no separate weekly formula).

    Every total here is a sum over the daily ledger, never recomputed with a
    different formula, so the daily breakdown and the totals can never
    silently disagree.
    """
    daily_breakdown = tuple(
        calculate_daily_capacity(day, schedules, exceptions, allocations)
        for day in iterate_dates(start_date, end_date)
    )
    gross_capacity = sum((day.scheduled_hours for day in daily_breakdown), ZERO)
    unavailable_hours = sum((day.unavailable_hours for day in daily_breakdown), ZERO)
    effective_capacity = sum((day.effective_capacity for day in daily_breakdown), ZERO)
    allocated_hours = sum((day.allocated_hours for day in daily_breakdown), ZERO)
    remaining_capacity = effective_capacity - allocated_hours
    over_allocation = max(allocated_hours - effective_capacity, ZERO)
    utilization = (
        _quantize_utilization(allocated_hours / effective_capacity)
        if effective_capacity > ZERO
        else None
    )
    return PersonCapacityResult(
        start_date=start_date,
        end_date=end_date,
        gross_capacity=gross_capacity,
        unavailable_hours=unavailable_hours,
        effective_capacity=effective_capacity,
        allocated_hours=allocated_hours,
        remaining_capacity=remaining_capacity,
        utilization=utilization,
        over_allocation=over_allocation,
        daily_breakdown=daily_breakdown,
    )


def aggregate_team_capacity(
    start_date: date,
    end_date: date,
    members: Sequence[PersonCapacityResult],
) -> TeamCapacityResult:
    """Team totals from member totals (spec §18) — start_date/end_date are
    explicit parameters (not inferred from members) so an empty team still
    returns a well-formed zero result for the requested range.

    Utilization is WEIGHTED — sum(allocated) / sum(effective) — never an
    average of member utilization percentages, which would misrepresent a
    team of unevenly-sized capacities (decision #6). over_allocation and
    remaining_capacity are likewise derived from team totals with the same
    formula used at the person level, not by summing each member's
    over_allocation (which would double-count instead of reflecting net
    team-level slack). This never hides an individual's over-allocation: the
    service layer returns each member's own PersonCapacityResult alongside
    this aggregate.
    """
    gross_capacity = sum((member.gross_capacity for member in members), ZERO)
    unavailable_hours = sum((member.unavailable_hours for member in members), ZERO)
    effective_capacity = sum((member.effective_capacity for member in members), ZERO)
    allocated_hours = sum((member.allocated_hours for member in members), ZERO)
    remaining_capacity = effective_capacity - allocated_hours
    over_allocation = max(allocated_hours - effective_capacity, ZERO)
    utilization = (
        _quantize_utilization(allocated_hours / effective_capacity)
        if effective_capacity > ZERO
        else None
    )
    return TeamCapacityResult(
        start_date=start_date,
        end_date=end_date,
        gross_capacity=gross_capacity,
        unavailable_hours=unavailable_hours,
        effective_capacity=effective_capacity,
        allocated_hours=allocated_hours,
        remaining_capacity=remaining_capacity,
        utilization=utilization,
        over_allocation=over_allocation,
    )


# ---------------------------------------------------------------------------
# Project demand — allocated hours only, no effective-capacity concept
# (spec §19: a project has demand, not capacity of its own; no forecasting)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectAllocationFact:
    """A project's allocation tagged with who it's for, so demand can be
    broken down by person as well as by day."""

    person_id: uuid.UUID
    allocation: AllocationFact


@dataclass(frozen=True)
class ProjectDailyDemand:
    date: date
    allocated_hours: Decimal


@dataclass(frozen=True)
class ProjectPersonDemand:
    person_id: uuid.UUID
    allocated_hours: Decimal


@dataclass(frozen=True)
class ProjectDemandResult:
    start_date: date
    end_date: date
    allocated_hours: Decimal
    allocated_people: int
    daily_breakdown: tuple[ProjectDailyDemand, ...]
    by_person: tuple[ProjectPersonDemand, ...]


def calculate_project_demand(
    start_date: date,
    end_date: date,
    allocations: Sequence[ProjectAllocationFact],
) -> ProjectDemandResult:
    """How much allocation this project has drawn during [start_date, end_date],
    in total, by day, and by person — using the same time-phasing as person-
    level capacity (allocation_amount_for_date) so the two are always
    consistent. Deliberately does not compute or compare against anyone's
    effective capacity: that's a person/team question, not a project one.
    """
    daily_breakdown: list[ProjectDailyDemand] = []
    person_totals: dict[uuid.UUID, Decimal] = {}
    for day in iterate_dates(start_date, end_date):
        day_total = ZERO
        for entry in allocations:
            amount = allocation_amount_for_date(entry.allocation, day)
            if amount > ZERO:
                day_total += amount
                person_totals[entry.person_id] = person_totals.get(entry.person_id, ZERO) + amount
        daily_breakdown.append(ProjectDailyDemand(date=day, allocated_hours=day_total))

    allocated_hours = sum((day.allocated_hours for day in daily_breakdown), ZERO)
    by_person = tuple(
        ProjectPersonDemand(person_id=person_id, allocated_hours=person_totals[person_id])
        for person_id in sorted(person_totals, key=str)
    )
    return ProjectDemandResult(
        start_date=start_date,
        end_date=end_date,
        allocated_hours=allocated_hours,
        allocated_people=len(by_person),
        daily_breakdown=tuple(daily_breakdown),
        by_person=by_person,
    )

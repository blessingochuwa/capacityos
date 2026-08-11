import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DailyCapacityRead(BaseModel):
    """One day's full capacity picture. utilization is null (not 0) when
    effective_capacity is 0 — see PersonCapacityRead.utilization."""

    date: date
    scheduled_hours: Decimal
    unavailable_hours: Decimal
    effective_capacity: Decimal
    allocated_hours: Decimal
    remaining_capacity: Decimal
    utilization: Decimal | None
    over_allocation: Decimal


class PersonCapacityRead(BaseModel):
    """A person's capacity over [start_date, end_date]. gross_capacity/
    unavailable_hours/effective_capacity/allocated_hours are facts derived
    from WorkingSchedule + AvailabilityException + Allocation; remaining_capacity/
    utilization/over_allocation are further derived from those. utilization is
    null when effective_capacity is 0 (there's nothing to divide by — 0%
    would misleadingly suggest available-but-unused capacity, not "no
    capacity in this period" — see docs/domain-concepts.md)."""

    person_id: uuid.UUID
    start_date: date
    end_date: date
    gross_capacity: Decimal
    unavailable_hours: Decimal
    effective_capacity: Decimal
    allocated_hours: Decimal
    remaining_capacity: Decimal
    utilization: Decimal | None
    over_allocation: Decimal
    daily_breakdown: list[DailyCapacityRead]


class TeamCapacityRead(BaseModel):
    """Team totals are sums of member totals; utilization is WEIGHTED
    (sum(allocated) / sum(effective)), never an average of member
    utilization percentages — see docs/adr/0003-phase-2-capacity-engine.md.
    members preserves each person's own result so no individual
    over-allocation is hidden by the team aggregate."""

    team_id: uuid.UUID
    start_date: date
    end_date: date
    gross_capacity: Decimal
    unavailable_hours: Decimal
    effective_capacity: Decimal
    allocated_hours: Decimal
    remaining_capacity: Decimal
    utilization: Decimal | None
    over_allocation: Decimal
    members: list[PersonCapacityRead]


class ProjectDailyDemandRead(BaseModel):
    date: date
    allocated_hours: Decimal


class ProjectPersonDemandRead(BaseModel):
    person_id: uuid.UUID
    allocated_hours: Decimal


class ProjectDemandRead(BaseModel):
    """Allocated hours for a project over [start_date, end_date] — demand
    only, no capacity/forecasting concept (a project has no working schedule
    of its own to compare against)."""

    project_id: uuid.UUID
    start_date: date
    end_date: date
    allocated_hours: Decimal
    allocated_people: int
    daily_breakdown: list[ProjectDailyDemandRead]
    by_person: list[ProjectPersonDemandRead]

"""Turns ORM rows into the plain fact dataclasses the capacity engine
(app/domain/capacity.py) consumes.

Extracted from app/services/capacity.py (Phase 2) so the scenario planning
layer (Phase 4, app/services/scenario_calculation.py) can build the exact
same facts for a hypothetical/overlaid planning state without duplicating
this conversion or its batched-query shape. CapacityService and
ScenarioCalculationService both call load_people_facts — there is exactly
one place ORM rows become facts.
"""

import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date

from app.domain.capacity import AllocationFact, AvailabilityExceptionFact, ScheduleFact
from app.models.allocation import Allocation
from app.models.availability_exception import AvailabilityException
from app.models.working_schedule import WorkingSchedule
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.working_schedule import WorkingScheduleRepository


def schedule_to_fact(schedule: WorkingSchedule) -> ScheduleFact:
    return ScheduleFact(
        effective_start_date=schedule.effective_start_date,
        effective_end_date=schedule.effective_end_date,
        entries={entry.weekday: entry.hours for entry in schedule.entries},
        created_at=schedule.created_at,
    )


def exception_to_fact(exception: AvailabilityException) -> AvailabilityExceptionFact:
    return AvailabilityExceptionFact(
        start_date=exception.start_date, end_date=exception.end_date, hours=exception.hours
    )


def allocation_to_fact(allocation: Allocation) -> AllocationFact:
    return AllocationFact(
        start_date=allocation.start_date,
        end_date=allocation.end_date,
        allocation_hours=allocation.allocation_hours,
    )


def group_by[T](items: Sequence[T], key: Callable[[T], uuid.UUID]) -> dict[uuid.UUID, list[T]]:
    grouped: dict[uuid.UUID, list[T]] = defaultdict(list)
    for item in items:
        grouped[key(item)].append(item)
    return grouped


@dataclass(frozen=True)
class PersonPlanningFacts:
    """One person's baseline facts for [start_date, end_date] — the input
    the capacity engine needs, with identifiers stripped (person_id is the
    dict key in PlanningFacts.by_person, not carried on this dataclass)."""

    schedules: tuple[ScheduleFact, ...] = field(default_factory=tuple)
    exceptions: tuple[AvailabilityExceptionFact, ...] = field(default_factory=tuple)
    allocations: tuple[AllocationFact, ...] = field(default_factory=tuple)


def load_people_facts(
    schedule_repository: WorkingScheduleRepository,
    availability_repository: AvailabilityExceptionRepository,
    allocation_repository: AllocationRepository,
    person_ids: Sequence[uuid.UUID],
    start_date: date,
    end_date: date,
    organization_id: uuid.UUID,
) -> dict[uuid.UUID, PersonPlanningFacts]:
    """Batched fact-loading for person_ids over [start_date, end_date] — one
    query per fact type for the whole set (CLAUDE.md §27: no per-person
    queries), matching the shape CapacityService.get_team_capacity already
    used before this was extracted.

    person_ids with no rows for some/all fact types still get an entry
    (empty tuples), so callers can rely on every requested id being a key.

    organization_id (Phase 12) is threaded into every underlying query as
    defense-in-depth — every caller already resolves person_ids from an
    organization-scoped source (team membership, a single already-org-
    checked person, etc.), but this is the single shared interception
    point every capacity/scenario/insight/skill calculation that touches
    schedules, availability exceptions, or allocations routes through, so
    it carries the check explicitly rather than trusting every caller
    forever. See docs/adr/0012-organizations-multi-tenancy.md.
    """
    ids = list(person_ids)
    schedules_by_person = group_by(
        schedule_repository.list_for_people(ids, start_date, end_date, organization_id),
        lambda s: s.person_id,
    )
    exceptions_by_person = group_by(
        availability_repository.list_for_people(ids, start_date, end_date, organization_id),
        lambda e: e.person_id,
    )
    allocations_by_person = group_by(
        allocation_repository.list_for_people(ids, start_date, end_date, organization_id),
        lambda a: a.person_id,
    )

    return {
        person_id: PersonPlanningFacts(
            schedules=tuple(schedule_to_fact(s) for s in schedules_by_person.get(person_id, [])),
            exceptions=tuple(
                exception_to_fact(e) for e in exceptions_by_person.get(person_id, [])
            ),
            allocations=tuple(
                allocation_to_fact(a) for a in allocations_by_person.get(person_id, [])
            ),
        )
        for person_id in ids
    }

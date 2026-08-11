import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date

from app.core.exceptions import DomainValidationError, NotFoundError
from app.domain.capacity import (
    AllocationFact,
    AvailabilityExceptionFact,
    PersonCapacityResult,
    ProjectAllocationFact,
    ProjectDemandResult,
    ScheduleFact,
    TeamCapacityResult,
    aggregate_team_capacity,
    calculate_period_capacity,
    calculate_project_demand,
)
from app.models.allocation import Allocation
from app.models.availability_exception import AvailabilityException
from app.models.working_schedule import WorkingSchedule
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.team import TeamRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository

MAX_RANGE_DAYS = 1096
"""~3 years. A pragmatic guard (decision #7) against a typo'd date range
blowing up the size of the daily breakdown — not a business rule."""


def _schedule_to_fact(schedule: WorkingSchedule) -> ScheduleFact:
    return ScheduleFact(
        effective_start_date=schedule.effective_start_date,
        effective_end_date=schedule.effective_end_date,
        entries={entry.weekday: entry.hours for entry in schedule.entries},
        created_at=schedule.created_at,
    )


def _exception_to_fact(exception: AvailabilityException) -> AvailabilityExceptionFact:
    return AvailabilityExceptionFact(
        start_date=exception.start_date, end_date=exception.end_date, hours=exception.hours
    )


def _allocation_to_fact(allocation: Allocation) -> AllocationFact:
    return AllocationFact(
        start_date=allocation.start_date,
        end_date=allocation.end_date,
        allocation_hours=allocation.allocation_hours,
    )


def _group_by[T](items: Sequence[T], key: Callable[[T], uuid.UUID]) -> dict[uuid.UUID, list[T]]:
    grouped: dict[uuid.UUID, list[T]] = defaultdict(list)
    for item in items:
        grouped[key(item)].append(item)
    return grouped


class CapacityService:
    """Orchestrates the repositories and the pure domain engine
    (app/domain/capacity.py) to answer capacity questions. Holds no
    calculation logic itself — see CLAUDE.md §10/§22 (repositories fetch
    facts, the domain layer calculates, this layer assembles the two)."""

    def __init__(
        self,
        schedule_repository: WorkingScheduleRepository,
        availability_repository: AvailabilityExceptionRepository,
        allocation_repository: AllocationRepository,
        person_repository: PersonRepository,
        team_repository: TeamRepository,
        team_membership_repository: TeamMembershipRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self.schedule_repository = schedule_repository
        self.availability_repository = availability_repository
        self.allocation_repository = allocation_repository
        self.person_repository = person_repository
        self.team_repository = team_repository
        self.team_membership_repository = team_membership_repository
        self.project_repository = project_repository

    def _validate_range(self, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise DomainValidationError("end_date cannot precede start_date")
        if (end_date - start_date).days + 1 > MAX_RANGE_DAYS:
            raise DomainValidationError(f"date range cannot exceed {MAX_RANGE_DAYS} days")

    def _person_capacity(
        self, person_id: uuid.UUID, start_date: date, end_date: date
    ) -> PersonCapacityResult:
        schedules = self.schedule_repository.list_for_people([person_id], start_date, end_date)
        exceptions = self.availability_repository.list_for_people([person_id], start_date, end_date)
        allocations = self.allocation_repository.list_for_people([person_id], start_date, end_date)
        return calculate_period_capacity(
            start_date,
            end_date,
            [_schedule_to_fact(s) for s in schedules],
            [_exception_to_fact(e) for e in exceptions],
            [_allocation_to_fact(a) for a in allocations],
        )

    def get_person_capacity(
        self, person_id: uuid.UUID, start_date: date, end_date: date
    ) -> PersonCapacityResult:
        self._validate_range(start_date, end_date)
        if self.person_repository.get(person_id) is None:
            raise NotFoundError("Person", person_id)
        return self._person_capacity(person_id, start_date, end_date)

    def get_team_capacity(
        self, team_id: uuid.UUID, start_date: date, end_date: date
    ) -> tuple[TeamCapacityResult, list[tuple[uuid.UUID, PersonCapacityResult]]]:
        """Returns the team aggregate alongside each member's own result, so
        an individual's over-allocation is never hidden by the team total
        (see aggregate_team_capacity's docstring)."""
        self._validate_range(start_date, end_date)
        if self.team_repository.get(team_id) is None:
            raise NotFoundError("Team", team_id)

        person_ids = [
            membership.person_id
            for membership in self.team_membership_repository.list_for_team(team_id)
        ]

        schedules_by_person = _group_by(
            self.schedule_repository.list_for_people(person_ids, start_date, end_date),
            lambda s: s.person_id,
        )
        exceptions_by_person = _group_by(
            self.availability_repository.list_for_people(person_ids, start_date, end_date),
            lambda e: e.person_id,
        )
        allocations_by_person = _group_by(
            self.allocation_repository.list_for_people(person_ids, start_date, end_date),
            lambda a: a.person_id,
        )

        members: list[tuple[uuid.UUID, PersonCapacityResult]] = []
        for person_id in person_ids:
            result = calculate_period_capacity(
                start_date,
                end_date,
                [_schedule_to_fact(s) for s in schedules_by_person.get(person_id, [])],
                [_exception_to_fact(e) for e in exceptions_by_person.get(person_id, [])],
                [_allocation_to_fact(a) for a in allocations_by_person.get(person_id, [])],
            )
            members.append((person_id, result))

        team_result = aggregate_team_capacity(
            start_date, end_date, [result for _, result in members]
        )
        return team_result, members

    def get_project_demand(
        self, project_id: uuid.UUID, start_date: date, end_date: date
    ) -> ProjectDemandResult:
        self._validate_range(start_date, end_date)
        if self.project_repository.get(project_id) is None:
            raise NotFoundError("Project", project_id)

        allocations = self.allocation_repository.list_for_project(project_id, start_date, end_date)
        facts = [
            ProjectAllocationFact(
                person_id=allocation.person_id, allocation=_allocation_to_fact(allocation)
            )
            for allocation in allocations
        ]
        return calculate_project_demand(start_date, end_date, facts)

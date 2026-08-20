import uuid
from datetime import date

from app.core.exceptions import DomainValidationError, NotFoundError
from app.domain.capacity import (
    PersonCapacityResult,
    ProjectAllocationFact,
    ProjectDemandResult,
    TeamCapacityResult,
    aggregate_team_capacity,
    calculate_period_capacity,
    calculate_project_demand,
)
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.team import TeamRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.services.planning_facts import allocation_to_fact, load_people_facts

MAX_RANGE_DAYS = 1096
"""~3 years. A pragmatic guard (decision #7) against a typo'd date range
blowing up the size of the daily breakdown — not a business rule."""


class CapacityService:
    """Orchestrates the repositories and the pure domain engine
    (app/domain/capacity.py) to answer capacity questions. Holds no
    calculation logic itself — see CLAUDE.md §10/§22 (repositories fetch
    facts, the domain layer calculates, this layer assembles the two).
    Organization-scoped (Phase 12) — every entry point takes
    organization_id, resolved by the route from Depends(get_current_
    membership)."""

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
        self, organization_id: uuid.UUID, person_id: uuid.UUID, start_date: date, end_date: date
    ) -> PersonCapacityResult:
        facts = load_people_facts(
            self.schedule_repository,
            self.availability_repository,
            self.allocation_repository,
            [person_id],
            start_date,
            end_date,
            organization_id,
        )[person_id]
        return calculate_period_capacity(
            start_date,
            end_date,
            list(facts.schedules),
            list(facts.exceptions),
            list(facts.allocations),
        )

    def get_person_capacity(
        self, organization_id: uuid.UUID, person_id: uuid.UUID, start_date: date, end_date: date
    ) -> PersonCapacityResult:
        self._validate_range(start_date, end_date)
        if self.person_repository.get(person_id, organization_id) is None:
            raise NotFoundError("Person", person_id)
        return self._person_capacity(organization_id, person_id, start_date, end_date)

    def get_team_capacity(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, start_date: date, end_date: date
    ) -> tuple[TeamCapacityResult, list[tuple[uuid.UUID, PersonCapacityResult]]]:
        """Returns the team aggregate alongside each member's own result, so
        an individual's over-allocation is never hidden by the team total
        (see aggregate_team_capacity's docstring)."""
        self._validate_range(start_date, end_date)
        if self.team_repository.get(team_id, organization_id) is None:
            raise NotFoundError("Team", team_id)

        person_ids = [
            membership.person_id
            for membership in self.team_membership_repository.list_for_team(
                team_id, organization_id
            )
        ]

        facts_by_person = load_people_facts(
            self.schedule_repository,
            self.availability_repository,
            self.allocation_repository,
            person_ids,
            start_date,
            end_date,
            organization_id,
        )

        members: list[tuple[uuid.UUID, PersonCapacityResult]] = []
        for person_id in person_ids:
            facts = facts_by_person[person_id]
            result = calculate_period_capacity(
                start_date,
                end_date,
                list(facts.schedules),
                list(facts.exceptions),
                list(facts.allocations),
            )
            members.append((person_id, result))

        team_result = aggregate_team_capacity(
            start_date, end_date, [result for _, result in members]
        )
        return team_result, members

    def get_project_demand(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, start_date: date, end_date: date
    ) -> ProjectDemandResult:
        self._validate_range(start_date, end_date)
        if self.project_repository.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)

        allocations = self.allocation_repository.list_for_project(
            project_id, start_date, end_date, organization_id
        )
        facts = [
            ProjectAllocationFact(
                person_id=allocation.person_id, allocation=allocation_to_fact(allocation)
            )
            for allocation in allocations
        ]
        return calculate_project_demand(start_date, end_date, facts)

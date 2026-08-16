"""Small, deterministic builders for domain objects used across tests.

Explicit keyword parameters (not **overrides: dict) so callers get real type
checking on what they override, and so Pyright strict mode can verify every
call site — matches app/models' own explicitness.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.availability_exception import AvailabilityException
from app.models.enums import AllocationUnit, AvailabilityType, EmploymentStatus, ProjectStatus
from app.models.person import Person
from app.models.project import Project
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.working_schedule import WorkingSchedule, WorkingScheduleEntry


def make_person(
    session: Session,
    *,
    first_name: str = "Alex",
    last_name: str = "Morgan",
    display_name: str | None = None,
    email: str = "alex.morgan@example.com",
    job_title: str | None = "Senior Product Designer",
    timezone: str = "UTC",
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE,
) -> Person:
    person = Person(
        first_name=first_name,
        last_name=last_name,
        display_name=display_name or f"{first_name} {last_name}",
        email=email,
        job_title=job_title,
        timezone=timezone,
        employment_status=employment_status,
    )
    session.add(person)
    session.flush()
    return person


def make_team(
    session: Session, *, name: str = "Creative", description: str | None = None
) -> Team:
    team = Team(name=name, description=description)
    session.add(team)
    session.flush()
    return team


def make_team_membership(session: Session, *, person: Person, team: Team) -> TeamMembership:
    membership = TeamMembership(person_id=person.id, team_id=team.id)
    session.add(membership)
    session.flush()
    return membership


def make_project(
    session: Session,
    *,
    name: str = "Website Redesign",
    description: str | None = None,
    status: ProjectStatus = ProjectStatus.PLANNED,
    start_date: date | None = date(2026, 9, 1),
    end_date: date | None = date(2026, 10, 31),
    external_id: str | None = None,
) -> Project:
    project = Project(
        name=name,
        description=description,
        status=status,
        start_date=start_date,
        end_date=end_date,
        external_id=external_id,
    )
    session.add(project)
    session.flush()
    return project


def make_allocation(
    session: Session,
    *,
    person: Person,
    project: Project,
    start_date: date = date(2026, 9, 1),
    end_date: date = date(2026, 9, 30),
    allocation_hours: Decimal = Decimal("20"),
    allocation_unit: AllocationUnit = AllocationUnit.TOTAL_HOURS,
    notes: str | None = None,
    external_id: str | None = None,
) -> Allocation:
    allocation = Allocation(
        person_id=person.id,
        project_id=project.id,
        start_date=start_date,
        end_date=end_date,
        allocation_hours=allocation_hours,
        allocation_unit=allocation_unit,
        notes=notes,
        external_id=external_id,
    )
    session.add(allocation)
    session.flush()
    return allocation


def make_working_schedule(
    session: Session,
    *,
    person: Person,
    entries: list[WorkingScheduleEntry] | None = None,
    effective_start_date: date | None = None,
    effective_end_date: date | None = None,
    external_id: str | None = None,
) -> WorkingSchedule:
    schedule = WorkingSchedule(
        person_id=person.id,
        effective_start_date=effective_start_date,
        effective_end_date=effective_end_date,
        external_id=external_id,
        entries=entries
        if entries is not None
        else [WorkingScheduleEntry(weekday=weekday, hours=Decimal("8")) for weekday in range(5)],
    )
    session.add(schedule)
    session.flush()
    return schedule


def make_availability_exception(
    session: Session,
    *,
    person: Person,
    start_date: date = date(2026, 9, 15),
    end_date: date = date(2026, 9, 19),
    availability_type: AvailabilityType = AvailabilityType.ANNUAL_LEAVE,
    hours: Decimal | None = None,
    notes: str | None = None,
    external_id: str | None = None,
) -> AvailabilityException:
    exception = AvailabilityException(
        person_id=person.id,
        start_date=start_date,
        end_date=end_date,
        availability_type=availability_type,
        hours=hours,
        notes=notes,
        external_id=external_id,
    )
    session.add(exception)
    session.flush()
    return exception

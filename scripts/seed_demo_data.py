"""Seed ONE organization with reproducible, fictional DEMO DATA.

DEMO DATA != PRODUCTION DATA (CLAUDE.md §26). This script exists so a
prototype or local environment has a realistic capacity-planning situation
to explore. It is not wired into any application code path or API route and
must be run explicitly by an operator.

Usage (from apps/api, so DATABASE_URL/.env resolve exactly as the API does):

    uv run python -m alembic upgrade head
    uv run python ../../scripts/seed_demo_data.py --organization-slug default
    uv run python ../../scripts/seed_demo_data.py --organization-slug default --week-of 2026-11-02

Behaviour (see docs/production-readiness.md, "Demo data"):

- **Explicit target.** The organization is chosen by slug; nothing is ever
  seeded into an organization that wasn't named. An unknown or inactive slug
  exits with status 2 and changes nothing.
- **Idempotent per organization.** If the organization already contains the
  "Product Design (Demo)" team, the script reports that and exits 0 without
  writing anything.
- **Atomic.** Everything is written in one transaction through the service
  layer (the same validation a real API request gets). Any error rolls the
  whole seed back, so a failure never leaves a half-seeded organization.
- **Reproducible.** Every record is a fixed literal; no randomness. Dates
  are anchored to one Monday-to-Friday week (``--week-of``, default: the
  current week) so the data appears in the app's default "This week" view.
  Expected capacity values for that week are documented in
  docs/production-readiness.md and asserted by
  apps/api/tests/scripts/test_seed_demo_data.py.

All names and emails are fictional (``@example.com``).
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.enums import (  # noqa: E402
    AvailabilityType,
    ProjectStatus,
    SkillProficiency,
)
from app.repositories.allocation import AllocationRepository  # noqa: E402
from app.repositories.availability_exception import AvailabilityExceptionRepository  # noqa: E402
from app.repositories.organization import OrganizationRepository  # noqa: E402
from app.repositories.person import PersonRepository  # noqa: E402
from app.repositories.person_skill import PersonSkillRepository  # noqa: E402
from app.repositories.project import ProjectRepository  # noqa: E402
from app.repositories.project_skill_requirement import (  # noqa: E402
    ProjectSkillRequirementRepository,
)
from app.repositories.skill import SkillRepository  # noqa: E402
from app.repositories.team import TeamRepository  # noqa: E402
from app.repositories.team_membership import TeamMembershipRepository  # noqa: E402
from app.repositories.working_schedule import WorkingScheduleRepository  # noqa: E402
from app.schemas.allocation import AllocationCreate  # noqa: E402
from app.schemas.availability_exception import AvailabilityExceptionCreate  # noqa: E402
from app.schemas.person import PersonCreate  # noqa: E402
from app.schemas.person_skill import PersonSkillCreate  # noqa: E402
from app.schemas.project import ProjectCreate  # noqa: E402
from app.schemas.project_skill_requirement import ProjectSkillRequirementCreate  # noqa: E402
from app.schemas.skill import SkillCreate  # noqa: E402
from app.schemas.team import TeamCreate  # noqa: E402
from app.schemas.team_membership import TeamMembershipCreate  # noqa: E402
from app.schemas.working_schedule import (  # noqa: E402
    WorkingScheduleCreate,
    WorkingScheduleEntryCreate,
)
from app.services.allocation import AllocationService  # noqa: E402
from app.services.availability_exception import AvailabilityExceptionService  # noqa: E402
from app.services.person import PersonService  # noqa: E402
from app.services.person_skill import PersonSkillService  # noqa: E402
from app.services.project import ProjectService  # noqa: E402
from app.services.project_skill_requirement import ProjectSkillRequirementService  # noqa: E402
from app.services.skill import SkillService  # noqa: E402
from app.services.team import TeamService  # noqa: E402
from app.services.team_membership import TeamMembershipService  # noqa: E402
from app.services.working_schedule import WorkingScheduleService  # noqa: E402

MARKER_TEAM = "Product Design (Demo)"
"""Presence of this team in an organization means it was already seeded."""

EXIT_OK = 0
EXIT_BAD_TARGET = 2
EXIT_FAILED = 1


class SeedTargetError(Exception):
    """The requested organization can't be seeded (unknown, inactive, or a
    bad --week-of). Nothing was written."""


@dataclass(frozen=True)
class SeedReport:
    organization_id: uuid.UUID
    week_start: dt.date
    created: bool
    """False when the organization was already seeded (nothing written)."""


@dataclass(frozen=True)
class _PersonSpec:
    key: str
    first_name: str
    last_name: str
    job_title: str
    team: str
    hours_by_weekday: dict[int, Decimal]
    """0=Monday .. 6=Sunday, matching WorkingScheduleEntryCreate.weekday."""


def _h(value: str) -> Decimal:
    return Decimal(value)


FULL_TIME = {weekday: _h("8") for weekday in range(5)}

TEAMS: dict[str, str] = {
    "design": MARKER_TEAM,
    "platform": "Platform Engineering (Demo)",
    "content": "Content & Motion (Demo)",
}

PEOPLE: Sequence[_PersonSpec] = (
    _PersonSpec("alex", "Alex", "Morgan", "Product Designer", "design", FULL_TIME),
    _PersonSpec("priya", "Priya", "Shah", "Senior Product Designer", "design", FULL_TIME),
    _PersonSpec("sam", "Sam", "Ade", "Design Lead", "design", FULL_TIME),
    _PersonSpec("taylor", "Taylor", "Brooks", "Backend Engineer", "platform", FULL_TIME),
    _PersonSpec("morgan", "Morgan", "Reyes", "Frontend Engineer", "platform", FULL_TIME),
    # Four-day week: 10h Monday-Thursday.
    _PersonSpec(
        "casey", "Casey", "Kim", "Platform Engineer", "platform",
        {weekday: _h("10") for weekday in range(4)},
    ),
    _PersonSpec("riley", "Riley", "Okafor", "Motion Designer", "content", FULL_TIME),
    # Part-time: 4h every weekday.
    _PersonSpec(
        "jamie", "Jamie", "Novak", "Motion Designer", "content",
        {weekday: _h("4") for weekday in range(5)},
    ),
    # Part-time: 6h Monday-Wednesday.
    _PersonSpec(
        "avery", "Avery", "Chen", "Content Strategist", "content",
        {weekday: _h("6") for weekday in range(3)},
    ),
)

PROJECTS: dict[str, tuple[str, ProjectStatus, str]] = {
    "website": ("Website Redesign (Demo)", ProjectStatus.ACTIVE, "DEMO-WEB"),
    "mobile": ("Mobile App Launch (Demo)", ProjectStatus.ACTIVE, "DEMO-MOB"),
    "tooling": ("Internal Tooling (Demo)", ProjectStatus.ACTIVE, "DEMO-TOOL"),
    "marketing": ("Q3 Marketing Site (Demo)", ProjectStatus.ACTIVE, "DEMO-MKT"),
    # The work a manager is deciding whether to accept: no allocations yet.
    "project_x": ("Project X (Proposed, Demo)", ProjectStatus.PLANNED, "DEMO-X"),
}

# (person, project, total hours, first weekday, last weekday) within the week.
# Every total divides exactly across its days, so per-day amounts are exact.
ALLOCATIONS: Sequence[tuple[str, str, str, int, int]] = (
    ("alex", "website", "28", 0, 4),
    ("priya", "website", "20", 0, 4),
    ("priya", "mobile", "16", 0, 4),
    ("sam", "website", "20", 0, 4),
    ("sam", "mobile", "20", 0, 4),
    ("taylor", "mobile", "32", 0, 4),
    ("morgan", "mobile", "24", 0, 4),
    ("morgan", "tooling", "12", 0, 4),
    ("casey", "tooling", "12", 0, 3),
    ("riley", "mobile", "24", 0, 4),
    ("riley", "marketing", "16", 0, 4),
    ("jamie", "marketing", "16", 0, 4),
    ("avery", "marketing", "8", 0, 1),
)

# (person, type, first weekday, last weekday, hours available that day or None)
AVAILABILITY: Sequence[tuple[str, AvailabilityType, int, int, str | None]] = (
    ("sam", AvailabilityType.ANNUAL_LEAVE, 4, 4, None),  # Friday off
    ("avery", AvailabilityType.TRAINING, 2, 2, "2"),  # only 2h available Wednesday
)

SKILLS: dict[str, tuple[str, str]] = {
    "motion": ("Motion Design", "Design"),
    "product_design": ("Product Design", "Design"),
    "frontend": ("Frontend Engineering", "Engineering"),
}

PERSON_SKILLS: Sequence[tuple[str, str, SkillProficiency]] = (
    ("riley", "motion", SkillProficiency.EXPERT),
    ("jamie", "motion", SkillProficiency.PROFICIENT),
    ("alex", "product_design", SkillProficiency.PROFICIENT),
    ("priya", "product_design", SkillProficiency.EXPERT),
    ("sam", "product_design", SkillProficiency.ADVANCED),
    ("morgan", "frontend", SkillProficiency.ADVANCED),
    ("taylor", "frontend", SkillProficiency.WORKING),
)

# Project X needs plenty of design (covered) but more motion design than the
# two motion designers have spare this week: the scarce-skill bottleneck.
REQUIREMENTS: Sequence[tuple[str, str, str, SkillProficiency]] = (
    ("project_x", "motion", "30", SkillProficiency.WORKING),
    ("project_x", "product_design", "16", SkillProficiency.WORKING),
    ("mobile", "motion", "24", SkillProficiency.WORKING),
)


def monday_of(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def _email(spec: _PersonSpec) -> str:
    return f"{spec.first_name}.{spec.last_name}".lower() + "@example.com"


def is_seeded(session: Session, organization_id: uuid.UUID) -> bool:
    return TeamRepository(session).get_by_name(MARKER_TEAM, organization_id) is not None


def seed_demo_organization(
    session: Session, organization_id: uuid.UUID, week_start: dt.date
) -> SeedReport:
    """Write the demo dataset into one organization. Flushes but never
    commits: the caller owns the transaction (see ``run``). Raises
    SeedTargetError for a week_start that isn't a Monday."""
    if week_start.weekday() != 0:
        raise SeedTargetError(f"--week-of must be a Monday; {week_start} is not.")
    if is_seeded(session, organization_id):
        return SeedReport(organization_id, week_start, created=False)

    org = organization_id
    people_repo = PersonRepository(session)
    team_repo = TeamRepository(session)
    project_repo = ProjectRepository(session)
    skill_repo = SkillRepository(session)

    def day(weekday: int) -> dt.date:
        return week_start + dt.timedelta(days=weekday)

    teams = TeamService(team_repo)
    team_ids = {
        key: teams.create(org, TeamCreate(name=name, description="DEMO DATA")).id
        for key, name in TEAMS.items()
    }

    projects = ProjectService(project_repo)
    project_ids = {
        key: projects.create(
            org,
            ProjectCreate(
                name=name,
                status=status,
                external_id=external_id,
                description="DEMO DATA",
                start_date=week_start,
                end_date=week_start + dt.timedelta(weeks=12),
            ),
        ).id
        for key, (name, status, external_id) in PROJECTS.items()
    }

    people = PersonService(people_repo)
    schedules = WorkingScheduleService(WorkingScheduleRepository(session), people_repo)
    memberships = TeamMembershipService(TeamMembershipRepository(session), people_repo, team_repo)
    person_ids: dict[str, uuid.UUID] = {}
    for spec in PEOPLE:
        person = people.create(
            org,
            PersonCreate(
                first_name=spec.first_name,
                last_name=spec.last_name,
                email=_email(spec),
                job_title=spec.job_title,
            ),
        )
        person_ids[spec.key] = person.id
        schedules.create(
            org,
            WorkingScheduleCreate(
                person_id=person.id,
                entries=[
                    WorkingScheduleEntryCreate(weekday=weekday, hours=hours)
                    for weekday, hours in spec.hours_by_weekday.items()
                ],
            ),
        )
        memberships.add_member(org, team_ids[spec.team], TeamMembershipCreate(person_id=person.id))

    exceptions = AvailabilityExceptionService(AvailabilityExceptionRepository(session), people_repo)
    for person_key, availability_type, first, last, hours in AVAILABILITY:
        exceptions.create(
            org,
            AvailabilityExceptionCreate(
                person_id=person_ids[person_key],
                start_date=day(first),
                end_date=day(last),
                availability_type=availability_type,
                hours=None if hours is None else _h(hours),
                notes="DEMO DATA",
            ),
        )

    allocations = AllocationService(AllocationRepository(session), people_repo, project_repo)
    for person_key, project_key, hours, first, last in ALLOCATIONS:
        allocations.create(
            org,
            AllocationCreate(
                person_id=person_ids[person_key],
                project_id=project_ids[project_key],
                start_date=day(first),
                end_date=day(last),
                allocation_hours=_h(hours),
            ),
        )

    skills = SkillService(skill_repo)
    skill_ids = {
        key: skills.create(org, SkillCreate(name=name, category=category)).id
        for key, (name, category) in SKILLS.items()
    }
    person_skills = PersonSkillService(PersonSkillRepository(session), people_repo, skill_repo)
    for person_key, skill_key, proficiency in PERSON_SKILLS:
        person_skills.add(
            org,
            person_ids[person_key],
            PersonSkillCreate(skill_id=skill_ids[skill_key], proficiency=proficiency),
        )
    requirements = ProjectSkillRequirementService(
        ProjectSkillRequirementRepository(session), project_repo, skill_repo
    )
    for project_key, skill_key, hours, minimum in REQUIREMENTS:
        requirements.add(
            org,
            project_ids[project_key],
            ProjectSkillRequirementCreate(
                skill_id=skill_ids[skill_key],
                required_hours=_h(hours),
                minimum_proficiency=minimum,
            ),
        )

    return SeedReport(organization_id, week_start, created=True)


def run(session: Session, organization_slug: str, week_start: dt.date) -> SeedReport:
    """Resolve the organization, seed it, and commit — or roll back
    everything on any error and re-raise."""
    organization = OrganizationRepository(session).get_by_slug(organization_slug)
    if organization is None:
        raise SeedTargetError(f"No organization with slug '{organization_slug}'.")
    if not organization.is_active:
        raise SeedTargetError(f"Organization '{organization_slug}' is deactivated.")
    try:
        report = seed_demo_organization(session, organization.id, week_start)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return report


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed one organization with DEMO DATA.")
    parser.add_argument(
        "--organization-slug",
        required=True,
        help="Slug of the organization to seed (the migration-created one is 'default').",
    )
    parser.add_argument(
        "--week-of",
        type=dt.date.fromisoformat,
        default=None,
        help="Any date in the week to anchor the data to (YYYY-MM-DD). Default: this week.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    week_start = monday_of(args.week_of or dt.date.today())
    session = SessionLocal()
    try:
        report = run(session, args.organization_slug, week_start)
    except SeedTargetError as error:
        print(f"Not seeded: {error}", file=sys.stderr)
        return EXIT_BAD_TARGET
    except Exception as error:
        print(
            f"Seed failed and was rolled back; nothing was written. "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return EXIT_FAILED
    finally:
        session.close()

    if report.created:
        print(
            f"Seeded organization '{args.organization_slug}' with DEMO DATA "
            f"for the week of {report.week_start.isoformat()}."
        )
    else:
        print(
            f"Organization '{args.organization_slug}' already has DEMO DATA "
            f"(found team '{MARKER_TEAM}'); nothing written."
        )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

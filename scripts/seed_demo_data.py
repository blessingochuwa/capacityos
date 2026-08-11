"""Seed CapacityOS with reproducible DEMO DATA — development only.

DEMO DATA != PRODUCTION DATA (CLAUDE.md §29). This script exists purely so
the Phase 3 UI has something realistic to render while developing/testing
it manually — it is not wired into any application code path, API route, or
production flow, and must be run explicitly and only against a development
database.

Reproducible per CLAUDE.md §25: every person, team, project, schedule,
allocation, and availability exception below is a fixed literal — no
`random`. Dates are anchored to *this calendar week* (Monday of the day the
script is run) purely so the data is immediately visible in the app's
default "This week" view; nothing about the scenario mix itself varies
between runs.

Deliberately built via the existing service layer (PersonService,
TeamService, ...), never raw SQL or direct model construction bypassing
validation — this script must go through the same rules a real API request
would (CLAUDE.md §6/§24).

Usage (from apps/api, so DATABASE_URL/.env resolve the same way the API
itself resolves them):

    uv run alembic upgrade head   # once, if not already applied
    uv run python ../../scripts/seed_demo_data.py

Safe to re-run: if the demo data already exists (detected by the "Product
Design" team), the script prints a message and exits without creating
duplicates or touching existing data.
"""

from __future__ import annotations

import datetime as dt
import sys
import uuid
from decimal import Decimal
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.models.enums import AvailabilityType  # noqa: E402
from app.repositories.allocation import AllocationRepository  # noqa: E402
from app.repositories.availability_exception import AvailabilityExceptionRepository  # noqa: E402
from app.repositories.person import PersonRepository  # noqa: E402
from app.repositories.project import ProjectRepository  # noqa: E402
from app.repositories.team import TeamRepository  # noqa: E402
from app.repositories.team_membership import TeamMembershipRepository  # noqa: E402
from app.repositories.working_schedule import WorkingScheduleRepository  # noqa: E402
from app.schemas.allocation import AllocationCreate  # noqa: E402
from app.schemas.availability_exception import AvailabilityExceptionCreate  # noqa: E402
from app.schemas.person import PersonCreate  # noqa: E402
from app.schemas.project import ProjectCreate  # noqa: E402
from app.schemas.team import TeamCreate  # noqa: E402
from app.schemas.team_membership import TeamMembershipCreate  # noqa: E402
from app.schemas.working_schedule import WorkingScheduleCreate, WorkingScheduleEntryCreate  # noqa: E402
from app.services.allocation import AllocationService  # noqa: E402
from app.services.availability_exception import AvailabilityExceptionService  # noqa: E402
from app.services.person import PersonService  # noqa: E402
from app.services.project import ProjectService  # noqa: E402
from app.services.team import TeamService  # noqa: E402
from app.services.team_membership import TeamMembershipService  # noqa: E402
from app.services.working_schedule import WorkingScheduleService  # noqa: E402

MONDAY = 0
FRIDAY = 4
FULL_TIME_WEEKDAYS = range(MONDAY, FRIDAY + 1)
FULL_TIME_HOURS = Decimal("8")


def monday_of(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


THIS_MONDAY = monday_of(dt.date.today())
THIS_FRIDAY = THIS_MONDAY + dt.timedelta(days=4)
THIS_TUESDAY = THIS_MONDAY + dt.timedelta(days=1)
THIS_WEDNESDAY = THIS_MONDAY + dt.timedelta(days=2)
THIS_THURSDAY = THIS_MONDAY + dt.timedelta(days=3)
NEXT_MONDAY = THIS_MONDAY + dt.timedelta(days=7)


def main() -> None:
    session = SessionLocal()
    try:
        team_repo = TeamRepository(session)
        if team_repo.get_by_name("Product Design") is not None:
            print("Demo data already present (found team 'Product Design') - skipping.")
            return

        people = PersonService(PersonRepository(session))
        teams = TeamService(team_repo)
        memberships = TeamMembershipService(
            TeamMembershipRepository(session), PersonRepository(session), team_repo
        )
        projects = ProjectService(ProjectRepository(session))
        schedules = WorkingScheduleService(WorkingScheduleRepository(session), PersonRepository(session))
        exceptions = AvailabilityExceptionService(
            AvailabilityExceptionRepository(session), PersonRepository(session)
        )
        allocations = AllocationService(
            AllocationRepository(session), PersonRepository(session), ProjectRepository(session)
        )

        # --- Teams -----------------------------------------------------
        design_team = teams.create(TeamCreate(name="Product Design", description="Design DEMO DATA"))
        platform_team = teams.create(
            TeamCreate(name="Platform Engineering", description="Engineering DEMO DATA")
        )

        # --- Projects ----------------------------------------------------
        website = projects.create(ProjectCreate(name="Website Redesign (Demo)", status="active"))
        mobile = projects.create(ProjectCreate(name="Mobile App Launch (Demo)", status="active"))
        tooling = projects.create(ProjectCreate(name="Internal Tooling (Demo)", status="active"))
        marketing = projects.create(ProjectCreate(name="Q3 Marketing Site (Demo)", status="planned"))

        def full_time_schedule(person_id: uuid.UUID) -> None:
            schedules.create(
                WorkingScheduleCreate(
                    person_id=person_id,
                    entries=[
                        WorkingScheduleEntryCreate(weekday=weekday, hours=FULL_TIME_HOURS)
                        for weekday in FULL_TIME_WEEKDAYS
                    ],
                )
            )

        # --- People ------------------------------------------------------
        # Healthy: ~70% utilized, single project.
        alex = people.create(
            PersonCreate(
                first_name="Alex",
                last_name="Morgan",
                email="alex.morgan@capacityos.demo",
                job_title="Product Designer",
            )
        )
        full_time_schedule(alex.id)
        memberships.add_member(design_team.id, TeamMembershipCreate(person_id=alex.id))
        allocations.create(
            AllocationCreate(
                person_id=alex.id,
                project_id=website.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("28"),
            )
        )

        # Near capacity: ~95%, two projects.
        priya = people.create(
            PersonCreate(
                first_name="Priya",
                last_name="Shah",
                email="priya.shah@capacityos.demo",
                job_title="Senior Product Designer",
            )
        )
        full_time_schedule(priya.id)
        memberships.add_member(design_team.id, TeamMembershipCreate(person_id=priya.id))
        allocations.create(
            AllocationCreate(
                person_id=priya.id,
                project_id=website.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("20"),
            )
        )
        allocations.create(
            AllocationCreate(
                person_id=priya.id,
                project_id=marketing.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("18"),
            )
        )

        # Over-allocated: two projects push them past effective capacity.
        sam = people.create(
            PersonCreate(
                first_name="Sam",
                last_name="Ade",
                email="sam.ade@capacityos.demo",
                job_title="Design Lead",
            )
        )
        full_time_schedule(sam.id)
        memberships.add_member(design_team.id, TeamMembershipCreate(person_id=sam.id))
        allocations.create(
            AllocationCreate(
                person_id=sam.id,
                project_id=website.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("24"),
            )
        )
        allocations.create(
            AllocationCreate(
                person_id=sam.id,
                project_id=mobile.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("20"),
            )
        )

        # Under-utilized: part-time schedule (4h Mon-Thu), light allocation.
        jordan = people.create(
            PersonCreate(
                first_name="Jordan",
                last_name="Lee",
                email="jordan.lee@capacityos.demo",
                job_title="UX Researcher",
            )
        )
        schedules.create(
            WorkingScheduleCreate(
                person_id=jordan.id,
                entries=[
                    WorkingScheduleEntryCreate(weekday=weekday, hours=Decimal("4"))
                    for weekday in range(MONDAY, MONDAY + 4)
                ],
            )
        )
        memberships.add_member(design_team.id, TeamMembershipCreate(person_id=jordan.id))
        allocations.create(
            AllocationCreate(
                person_id=jordan.id,
                project_id=website.id,
                start_date=THIS_MONDAY,
                end_date=THIS_THURSDAY,
                allocation_hours=Decimal("6"),
            )
        )

        # Near capacity, Platform Engineering.
        taylor = people.create(
            PersonCreate(
                first_name="Taylor",
                last_name="Brooks",
                email="taylor.brooks@capacityos.demo",
                job_title="Backend Engineer",
            )
        )
        full_time_schedule(taylor.id)
        memberships.add_member(platform_team.id, TeamMembershipCreate(person_id=taylor.id))
        allocations.create(
            AllocationCreate(
                person_id=taylor.id,
                project_id=mobile.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("34"),
            )
        )

        # Weekend time-phasing showcase: one allocation spans Fri-next Mon,
        # so Saturday/Sunday (0 scheduled hours) each pick up a slice of it —
        # a real over-allocation conflict on those specific days even though
        # the *week total* stays comfortably under effective capacity. This
        # is the concrete case for spec §39's "date range containing
        # weekends" and CLAUDE.md's "is the team actually constrained, or is
        # capacity simply unevenly distributed?".
        casey = people.create(
            PersonCreate(
                first_name="Casey",
                last_name="Kim",
                email="casey.kim@capacityos.demo",
                job_title="Frontend Engineer",
            )
        )
        full_time_schedule(casey.id)
        memberships.add_member(platform_team.id, TeamMembershipCreate(person_id=casey.id))
        allocations.create(
            AllocationCreate(
                person_id=casey.id,
                project_id=mobile.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("20"),
            )
        )
        allocations.create(
            AllocationCreate(
                person_id=casey.id,
                project_id=tooling.id,
                start_date=THIS_FRIDAY,
                end_date=NEXT_MONDAY,
                allocation_hours=Decimal("12"),
            )
        )

        # Partial availability: 4h/day (instead of the normal 8h) for two
        # days this week, via a "training" exception.
        morgan = people.create(
            PersonCreate(
                first_name="Morgan",
                last_name="Diaz",
                email="morgan.diaz@capacityos.demo",
                job_title="Platform Engineer",
            )
        )
        full_time_schedule(morgan.id)
        memberships.add_member(platform_team.id, TeamMembershipCreate(person_id=morgan.id))
        exceptions.create(
            AvailabilityExceptionCreate(
                person_id=morgan.id,
                start_date=THIS_TUESDAY,
                end_date=THIS_WEDNESDAY,
                availability_type=AvailabilityType.TRAINING,
                hours=Decimal("4"),
                notes="Platform onboarding training (demo)",
            )
        )
        allocations.create(
            AllocationCreate(
                person_id=morgan.id,
                project_id=tooling.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("16"),
            )
        )

        # Zero-capacity conflict: fully on leave all week, but still
        # allocated — the canonical "leave with allocation conflict" case
        # (spec §25/§14): effective capacity 0, utilization null, but
        # over-allocation is fully visible.
        riley = people.create(
            PersonCreate(
                first_name="Riley",
                last_name="Chen",
                email="riley.chen@capacityos.demo",
                job_title="QA Engineer",
            )
        )
        full_time_schedule(riley.id)
        memberships.add_member(platform_team.id, TeamMembershipCreate(person_id=riley.id))
        exceptions.create(
            AvailabilityExceptionCreate(
                person_id=riley.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                availability_type=AvailabilityType.ANNUAL_LEAVE,
                hours=None,
                notes="Annual leave (demo)",
            )
        )
        allocations.create(
            AllocationCreate(
                person_id=riley.id,
                project_id=mobile.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("16"),
            )
        )

        # Available capacity: light allocation, plenty of room.
        drew = people.create(
            PersonCreate(
                first_name="Drew",
                last_name="Patel",
                email="drew.patel@capacityos.demo",
                job_title="Engineering Manager",
            )
        )
        full_time_schedule(drew.id)
        memberships.add_member(platform_team.id, TeamMembershipCreate(person_id=drew.id))
        allocations.create(
            AllocationCreate(
                person_id=drew.id,
                project_id=tooling.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("10"),
            )
        )

        # Not on any team — exercises person/project views independent of
        # team membership.
        jamie = people.create(
            PersonCreate(
                first_name="Jamie",
                last_name="Rivera",
                email="jamie.rivera@capacityos.demo",
                job_title="Marketing Specialist",
            )
        )
        full_time_schedule(jamie.id)
        allocations.create(
            AllocationCreate(
                person_id=jamie.id,
                project_id=marketing.id,
                start_date=THIS_MONDAY,
                end_date=THIS_FRIDAY,
                allocation_hours=Decimal("22"),
            )
        )

        session.commit()
        print("Seeded DEMO DATA: 2 teams, 4 projects, 10 people.")
        print(f"Week anchor: {THIS_MONDAY.isoformat()} (Monday) - {THIS_FRIDAY.isoformat()} (Friday)")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

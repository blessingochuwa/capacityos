"""Phase 52 — scripts/seed_demo_data.py: organization-scoped, idempotent,
atomic, and producing the hand-calculated capacity picture documented in
docs/production-readiness.md ("Demo data")."""

import os
import subprocess
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import seed_demo_data
from fastapi.testclient import TestClient
from seed_demo_data import SeedTargetError, run, seed_demo_organization
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.domain.capacity import PersonCapacityResult, TeamCapacityResult
from app.models.allocation import Allocation
from app.models.organization import Organization
from app.models.person import Person
from app.models.project import Project
from app.models.skill import Skill
from app.models.team import Team
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_skill_requirement import ProjectSkillRequirementRepository
from app.repositories.skill import SkillRepository
from app.repositories.team import TeamRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.services.allocation import AllocationService
from app.services.capacity import CapacityService
from app.services.skill_capacity import SkillCapacityService
from tests.factories import make_organization

WEEK = date(2026, 11, 2)  # a Monday
FRIDAY = WEEK + timedelta(days=4)
API_ROOT = Path(__file__).resolve().parents[2]
SEED_SCRIPT = API_ROOT.parent.parent / "scripts" / "seed_demo_data.py"

# (gross, unavailable, effective, allocated, remaining, utilization, over_allocation)
# for Monday-Friday of the seeded week. Derived by hand from app/domain/capacity.py:
# allocations spread evenly over every day of their range, effective = min(schedule,
# exception hours), utilization = allocated / effective to 4 dp.
EXPECTED_PEOPLE: dict[str, tuple[str, ...]] = {
    "alex.morgan@example.com": ("40", "0", "40", "28", "12", "0.7000", "0"),
    "priya.shah@example.com": ("40", "0", "40", "36", "4", "0.9000", "0"),
    # Friday annual leave: 32h effective against 40h booked.
    "sam.ade@example.com": ("40", "8", "32", "40", "-8", "1.2500", "8"),
    "taylor.brooks@example.com": ("40", "0", "40", "32", "8", "0.8000", "0"),
    "morgan.reyes@example.com": ("40", "0", "40", "36", "4", "0.9000", "0"),
    # Four-day week (10h Mon-Thu): the person with clear spare capacity.
    "casey.kim@example.com": ("40", "0", "40", "12", "28", "0.3000", "0"),
    "riley.okafor@example.com": ("40", "0", "40", "40", "0", "1.0000", "0"),
    "jamie.novak@example.com": ("20", "0", "20", "16", "4", "0.8000", "0"),
    # 6h Mon-Wed, only 2h available Wednesday (training).
    "avery.chen@example.com": ("18", "4", "14", "8", "6", "0.5714", "0"),
}

EXPECTED_TEAMS: dict[str, tuple[str, ...]] = {
    # Team utilization is weighted (sum allocated / sum effective) and team
    # over_allocation is net, so Sam's 8h overload is hidden at team level
    # but visible on his own row — documented engine behaviour (ADR 0003).
    "Product Design (Demo)": ("120", "8", "112", "104", "8", "0.9286", "0"),
    "Platform Engineering (Demo)": ("120", "0", "120", "80", "40", "0.6667", "0"),
    "Content & Motion (Demo)": ("78", "4", "74", "64", "10", "0.8649", "0"),
}


def _seed(session: Session, organization: Organization) -> None:
    report = seed_demo_organization(session, organization.id, WEEK)
    assert report.created is True
    session.flush()


def _count(session: Session, model: type, organization_id: uuid.UUID) -> int:
    column = model.organization_id  # type: ignore[attr-defined]
    statement = select(func.count()).select_from(model).where(column == organization_id)
    return session.scalar(statement) or 0


def _counts(session: Session, organization_id: uuid.UUID) -> dict[str, int]:
    return {
        model.__name__: _count(session, model, organization_id)
        for model in (Team, Person, Project, Allocation, Skill)
    }


def _capacity_service(session: Session) -> CapacityService:
    return CapacityService(
        WorkingScheduleRepository(session),
        AvailabilityExceptionRepository(session),
        AllocationRepository(session),
        PersonRepository(session),
        TeamRepository(session),
        TeamMembershipRepository(session),
        ProjectRepository(session),
    )


def _expected(values: tuple[str, ...]) -> tuple[Decimal | None, ...]:
    return tuple(Decimal(value) for value in values)


def _actual(result: PersonCapacityResult | TeamCapacityResult) -> tuple[Decimal | None, ...]:
    """Decimal equality ignores exponent (Decimal("40") == Decimal("40.00")),
    so the comparison is exact without string formatting."""
    return (
        result.gross_capacity,
        result.unavailable_hours,
        result.effective_capacity,
        result.allocated_hours,
        result.remaining_capacity,
        result.utilization,
        result.over_allocation,
    )


# ---------------------------------------------------------------------------
# Dataset shape
# ---------------------------------------------------------------------------


def test_seeds_the_full_demo_dataset(db_session: Session, organization: Organization) -> None:
    _seed(db_session, organization)

    assert _counts(db_session, organization.id) == {
        "Team": 3,
        "Person": 9,
        "Project": 5,
        "Allocation": 13,
        "Skill": 3,
    }
    project_x = ProjectRepository(db_session).get_by_external_id("DEMO-X", organization.id)
    assert project_x is not None
    assert project_x.status == "planned"
    assert _count(db_session, Allocation, organization.id) == 13
    assert all(
        allocation.project_id != project_x.id
        for allocation in db_session.scalars(select(Allocation))
    ), "Project X is the proposed work and must start with no allocations"


def test_every_record_is_fictional(db_session: Session, organization: Organization) -> None:
    _seed(db_session, organization)
    emails = db_session.scalars(
        select(Person.email).where(Person.organization_id == organization.id)
    ).all()
    assert emails and all(email.endswith("@example.com") for email in emails)


# ---------------------------------------------------------------------------
# Capacity picture — real engine vs hand-calculated values
# ---------------------------------------------------------------------------


def test_person_capacity_matches_hand_calculated_values(
    db_session: Session, organization: Organization
) -> None:
    _seed(db_session, organization)
    capacity = _capacity_service(db_session)
    people = PersonRepository(db_session)

    for email, expected in EXPECTED_PEOPLE.items():
        person = people.get_by_email(email, organization.id)
        assert person is not None, email
        result = capacity.get_person_capacity(organization.id, person.id, WEEK, FRIDAY)
        assert _actual(result) == _expected(expected), email


def test_team_capacity_matches_hand_calculated_values(
    db_session: Session, organization: Organization
) -> None:
    _seed(db_session, organization)
    capacity = _capacity_service(db_session)
    teams = TeamRepository(db_session)

    for name, expected in EXPECTED_TEAMS.items():
        team = teams.get_by_name(name, organization.id)
        assert team is not None, name
        aggregate, members = capacity.get_team_capacity(organization.id, team.id, WEEK, FRIDAY)
        assert _actual(aggregate) == _expected(expected), name
        assert len(members) == 3


def test_project_x_exposes_a_motion_design_bottleneck(
    db_session: Session, organization: Organization
) -> None:
    """Design capacity covers Project X; motion design does not — the two
    motion designers have only 4h spare between them (CLAUDE.md §14)."""
    _seed(db_session, organization)
    project_x = ProjectRepository(db_session).get_by_external_id("DEMO-X", organization.id)
    assert project_x is not None
    service = SkillCapacityService(
        PersonSkillRepository(db_session),
        SkillRepository(db_session),
        PersonRepository(db_session),
        ProjectRepository(db_session),
        ProjectSkillRequirementRepository(db_session),
        TeamRepository(db_session),
        TeamMembershipRepository(db_session),
        WorkingScheduleRepository(db_session),
        AvailabilityExceptionRepository(db_session),
        AllocationRepository(db_session),
    )

    coverage = service.get_project_skill_coverage(organization.id, project_x.id, WEEK, FRIDAY)
    by_skill = {entry.skill_label: entry for entry in coverage.requirements}

    motion = by_skill["Motion Design"]
    assert (motion.required_hours, motion.qualified_available_hours, motion.gap_hours) == (
        Decimal("30"),
        Decimal("4.00"),
        Decimal("26.00"),
    )
    design = by_skill["Product Design"]
    assert (design.required_hours, design.qualified_available_hours, design.gap_hours) == (
        Decimal("16"),
        Decimal("16.00"),
        Decimal("0.00"),
    )


def test_accepting_project_x_work_makes_riley_newly_over_allocated(
    client: TestClient, db_session: Session
) -> None:
    """The scenario exercise the demo is built for: book Riley (the expert
    motion designer) 16h onto Project X and see the impact, through the real
    scenario API, without touching live data."""
    organization: Organization = client.organization  # type: ignore[attr-defined]
    _seed(db_session, organization)
    riley = PersonRepository(db_session).get_by_email("riley.okafor@example.com", organization.id)
    project_x = ProjectRepository(db_session).get_by_external_id("DEMO-X", organization.id)
    assert riley is not None and project_x is not None

    scenario = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Accept Project X",
            "baseline_start_date": WEEK.isoformat(),
            "baseline_end_date": FRIDAY.isoformat(),
        },
    ).json()
    added = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "add_allocation",
            "person_id": str(riley.id),
            "project_id": str(project_x.id),
            "hours": "16",
            "start_date": WEEK.isoformat(),
            "end_date": FRIDAY.isoformat(),
        },
    )
    assert added.status_code == 201, added.text
    assert client.post(f"/api/v1/scenarios/{scenario['id']}/calculate").status_code == 200

    comparison = client.get(f"/api/v1/scenarios/{scenario['id']}/comparison").json()
    # A scenario's aggregate is scoped to the people its operations touch
    # plus anyone already on the projects they reference
    # (ScenarioCalculationService._collect_scope). Project X has no existing
    # allocations, so the scope is Riley alone: 40h -> 56h.
    aggregate = comparison["aggregate"]
    assert aggregate["baseline"]["allocated_hours"] == "40.00"
    assert aggregate["scenario"]["allocated_hours"] == "56.00"
    assert aggregate["over_allocated_people"] == {"baseline": 0, "scenario": 1, "delta": 1}
    riley_row = next(p for p in comparison["people"] if p["person_id"] == str(riley.id))
    assert riley_row["newly_over_allocated"] is True
    assert riley_row["over_allocation"]["scenario"] == "16.00"
    assert riley_row["utilization"]["scenario"] == "1.4000"

    # Live data untouched.
    assert _count(db_session, Allocation, organization.id) == 13


# ---------------------------------------------------------------------------
# Idempotency, isolation, atomicity, target validation
# ---------------------------------------------------------------------------


def test_reseeding_the_same_organization_writes_nothing(
    db_session: Session, organization: Organization
) -> None:
    _seed(db_session, organization)
    before = _counts(db_session, organization.id)

    report = seed_demo_organization(db_session, organization.id, WEEK)

    assert report.created is False
    assert _counts(db_session, organization.id) == before


def test_seeding_one_organization_never_touches_another(db_session: Session) -> None:
    org_a = make_organization(db_session, slug="seed-a")
    org_b = make_organization(db_session, slug="seed-b")

    _seed(db_session, org_a)
    assert _counts(db_session, org_b.id) == {
        "Team": 0, "Person": 0, "Project": 0, "Allocation": 0, "Skill": 0,
    }

    # The same fictional emails/names are valid in a second organization.
    _seed(db_session, org_b)
    assert _counts(db_session, org_b.id) == _counts(db_session, org_a.id)


def test_a_failure_rolls_back_the_entire_seed(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    organization = make_organization(db_session, slug="seed-fail")
    db_session.commit()
    calls = {"n": 0}
    original = AllocationService.create

    def failing_create(self: AllocationService, *args: object, **kwargs: object) -> Allocation:
        calls["n"] += 1
        if calls["n"] == 5:
            raise RuntimeError("simulated failure mid-seed")
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(AllocationService, "create", failing_create)

    with pytest.raises(RuntimeError, match="simulated failure"):
        run(db_session, "seed-fail", WEEK)

    assert _counts(db_session, organization.id) == {
        "Team": 0, "Person": 0, "Project": 0, "Allocation": 0, "Skill": 0,
    }
    assert seed_demo_data.is_seeded(db_session, organization.id) is False


def test_unknown_organization_is_rejected(db_session: Session) -> None:
    with pytest.raises(SeedTargetError, match="No organization with slug 'missing'"):
        run(db_session, "missing", WEEK)


def test_deactivated_organization_is_rejected(db_session: Session) -> None:
    organization = make_organization(db_session, slug="seed-inactive")
    organization.is_active = False
    db_session.commit()

    with pytest.raises(SeedTargetError, match="deactivated"):
        run(db_session, "seed-inactive", WEEK)
    assert _counts(db_session, organization.id)["Team"] == 0


def test_week_start_must_be_a_monday(db_session: Session, organization: Organization) -> None:
    with pytest.raises(SeedTargetError, match="must be a Monday"):
        seed_demo_organization(db_session, organization.id, WEEK + timedelta(days=1))


# ---------------------------------------------------------------------------
# End to end: the real CLI against a freshly MIGRATED database (not create_all)
# ---------------------------------------------------------------------------


def test_cli_seeds_a_freshly_migrated_database(tmp_path: Path) -> None:
    db_url = f"sqlite:///{(tmp_path / 'seed.db').as_posix()}"
    env = {**os.environ, "DATABASE_URL": db_url}

    def call(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args], cwd=API_ROOT, env=env, capture_output=True, text=True
        )

    migrate = call("-m", "alembic", "upgrade", "head")
    assert migrate.returncode == 0, migrate.stderr

    first = call(str(SEED_SCRIPT), "--organization-slug", "default", "--week-of", WEEK.isoformat())
    assert first.returncode == 0, first.stderr
    assert "Seeded organization 'default'" in first.stdout

    second = call(str(SEED_SCRIPT), "--organization-slug", "default", "--week-of", WEEK.isoformat())
    assert second.returncode == 0, second.stderr
    assert "nothing written" in second.stdout

    missing = call(str(SEED_SCRIPT), "--organization-slug", "nope")
    assert missing.returncode == 2
    assert "No organization with slug 'nope'" in missing.stderr

    engine = create_engine(db_url)
    with engine.connect() as connection:
        people = connection.execute(text("SELECT count(*) FROM people")).scalar_one()
        allocations = connection.execute(text("SELECT count(*) FROM allocations")).scalar_one()
    engine.dispose()
    assert (people, allocations) == (9, 13)

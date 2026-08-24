"""Small, deterministic builders for domain objects used across tests.

Explicit keyword parameters (not **overrides: dict) so callers get real type
checking on what they override, and so Pyright strict mode can verify every
call site — matches app/models' own explicitness.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.availability_exception import AvailabilityException
from app.models.enums import (
    AllocationUnit,
    AvailabilityType,
    EmploymentStatus,
    MembershipStatus,
    ProjectStatus,
    RiskImpact,
    RiskProbability,
    RiskStatus,
    ScenarioStatus,
    SkillProficiency,
    StakeholderDecisionAuthority,
    StakeholderInfluence,
    StakeholderInterest,
    UserRole,
    UserStatus,
)
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.person import Person
from app.models.person_skill import PersonSkill
from app.models.project import Project
from app.models.project_access_grant import ProjectAccessGrant
from app.models.project_skill_requirement import ProjectSkillRequirement
from app.models.risk import Risk
from app.models.scenario import Scenario
from app.models.skill import Skill
from app.models.stakeholder import Stakeholder
from app.models.team import Team
from app.models.team_access_grant import TeamAccessGrant
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.models.working_schedule import WorkingSchedule, WorkingScheduleEntry


def make_organization(
    session: Session, *, name: str = "Test Organization", slug: str | None = None
) -> Organization:
    organization = Organization(
        name=name, slug=slug or f"test-org-{uuid.uuid4().hex[:8]}", is_active=True
    )
    session.add(organization)
    session.flush()
    return organization


def make_organization_membership(
    session: Session,
    *,
    user: User,
    organization: Organization,
    role: UserRole = UserRole.MEMBER,
    status: MembershipStatus = MembershipStatus.ACTIVE,
) -> OrganizationMembership:
    membership = OrganizationMembership(
        user_id=user.id, organization_id=organization.id, role=role, status=status
    )
    session.add(membership)
    session.flush()
    return membership


def make_user(
    session: Session,
    *,
    email: str = "user@example.com",
    display_name: str = "Test User",
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    """A persisted User row for tests that need a real FK target (e.g.
    TeamAccessGrant.user_id) but aren't exercising authentication itself —
    password_hash is a placeholder no login attempt ever verifies against,
    same convention as tests/conftest.py::make_test_user (which exists
    separately for dependency-override-based route authentication).

    role was removed in Phase 12 (see app/models/user.py) — a caller that
    needs this user to hold a role in an organization must create an
    OrganizationMembership separately via make_organization_membership."""
    user = User(
        email=email,
        password_hash="!unused! — see make_user docstring",
        display_name=display_name,
        status=status,
    )
    session.add(user)
    session.flush()
    return user


def make_person(
    session: Session,
    *,
    organization: Organization,
    first_name: str = "Alex",
    last_name: str = "Morgan",
    display_name: str | None = None,
    email: str = "alex.morgan@example.com",
    job_title: str | None = "Senior Product Designer",
    timezone: str = "UTC",
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE,
) -> Person:
    person = Person(
        organization_id=organization.id,
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
    session: Session,
    *,
    organization: Organization,
    name: str = "Creative",
    description: str | None = None,
) -> Team:
    team = Team(organization_id=organization.id, name=name, description=description)
    session.add(team)
    session.flush()
    return team


def make_team_membership(
    session: Session, *, organization: Organization, person: Person, team: Team
) -> TeamMembership:
    membership = TeamMembership(
        organization_id=organization.id, person_id=person.id, team_id=team.id
    )
    session.add(membership)
    session.flush()
    return membership


def make_project(
    session: Session,
    *,
    organization: Organization,
    name: str = "Website Redesign",
    description: str | None = None,
    status: ProjectStatus = ProjectStatus.PLANNED,
    start_date: date | None = date(2026, 9, 1),
    end_date: date | None = date(2026, 10, 31),
    external_id: str | None = None,
) -> Project:
    project = Project(
        organization_id=organization.id,
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
    organization: Organization,
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
        organization_id=organization.id,
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
    organization: Organization,
    person: Person,
    entries: list[WorkingScheduleEntry] | None = None,
    effective_start_date: date | None = None,
    effective_end_date: date | None = None,
    external_id: str | None = None,
) -> WorkingSchedule:
    schedule = WorkingSchedule(
        organization_id=organization.id,
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
    organization: Organization,
    person: Person,
    start_date: date = date(2026, 9, 15),
    end_date: date = date(2026, 9, 19),
    availability_type: AvailabilityType = AvailabilityType.ANNUAL_LEAVE,
    hours: Decimal | None = None,
    notes: str | None = None,
    external_id: str | None = None,
) -> AvailabilityException:
    exception = AvailabilityException(
        organization_id=organization.id,
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


def make_skill(
    session: Session,
    *,
    organization: Organization,
    name: str = "Backend Development",
    description: str | None = None,
    category: str | None = None,
    is_active: bool = True,
) -> Skill:
    skill = Skill(
        organization_id=organization.id,
        name=name,
        description=description,
        category=category,
        is_active=is_active,
    )
    session.add(skill)
    session.flush()
    return skill


def make_person_skill(
    session: Session,
    *,
    organization: Organization,
    person: Person,
    skill: Skill,
    proficiency: SkillProficiency = SkillProficiency.PROFICIENT,
    notes: str | None = None,
) -> PersonSkill:
    person_skill = PersonSkill(
        organization_id=organization.id,
        person_id=person.id,
        skill_id=skill.id,
        proficiency=proficiency,
        notes=notes,
    )
    session.add(person_skill)
    session.flush()
    return person_skill


def make_team_access_grant(
    session: Session,
    *,
    organization: Organization,
    user: User,
    team: Team,
    granted_by: User | None = None,
) -> TeamAccessGrant:
    grant = TeamAccessGrant(
        organization_id=organization.id,
        user_id=user.id,
        team_id=team.id,
        granted_by_user_id=granted_by.id if granted_by is not None else None,
    )
    session.add(grant)
    session.flush()
    return grant


def make_project_access_grant(
    session: Session,
    *,
    organization: Organization,
    user: User,
    project: Project,
    granted_by: User | None = None,
) -> ProjectAccessGrant:
    grant = ProjectAccessGrant(
        organization_id=organization.id,
        user_id=user.id,
        project_id=project.id,
        granted_by_user_id=granted_by.id if granted_by is not None else None,
    )
    session.add(grant)
    session.flush()
    return grant


def make_project_skill_requirement(
    session: Session,
    *,
    organization: Organization,
    project: Project,
    skill: Skill,
    required_hours: Decimal = Decimal("40"),
    minimum_proficiency: SkillProficiency | None = None,
    notes: str | None = None,
) -> ProjectSkillRequirement:
    requirement = ProjectSkillRequirement(
        organization_id=organization.id,
        project_id=project.id,
        skill_id=skill.id,
        required_hours=required_hours,
        minimum_proficiency=minimum_proficiency,
        notes=notes,
    )
    session.add(requirement)
    session.flush()
    return requirement


def make_risk(
    session: Session,
    *,
    organization: Organization,
    project: Project,
    description: str = "Key vendor may miss the delivery deadline",
    cause: str | None = None,
    potential_effect: str | None = None,
    probability: RiskProbability = RiskProbability.MEDIUM,
    impact: RiskImpact = RiskImpact.MEDIUM,
    response: str | None = None,
    owner: Person | None = None,
    status: RiskStatus = RiskStatus.OPEN,
    review_date: date | None = None,
) -> Risk:
    risk = Risk(
        organization_id=organization.id,
        project_id=project.id,
        description=description,
        cause=cause,
        potential_effect=potential_effect,
        probability=probability,
        impact=impact,
        response=response,
        owner_person_id=owner.id if owner is not None else None,
        status=status,
        review_date=review_date,
    )
    session.add(risk)
    session.flush()
    return risk


def make_stakeholder(
    session: Session,
    *,
    organization: Organization,
    project: Project,
    name: str = "Jordan Client",
    person: Person | None = None,
    role: str = "Sponsor",
    influence: StakeholderInfluence = StakeholderInfluence.MEDIUM,
    interest: StakeholderInterest = StakeholderInterest.MEDIUM,
    decision_authority: StakeholderDecisionAuthority = StakeholderDecisionAuthority.INFORMED,
    communication_needs: str | None = None,
) -> Stakeholder:
    stakeholder = Stakeholder(
        organization_id=organization.id,
        project_id=project.id,
        name=name,
        person_id=person.id if person is not None else None,
        role=role,
        influence=influence,
        interest=interest,
        decision_authority=decision_authority,
        communication_needs=communication_needs,
    )
    session.add(stakeholder)
    session.flush()
    return stakeholder


def make_scenario(
    session: Session,
    *,
    organization: Organization,
    name: str = "Q4 hiring plan",
    description: str | None = None,
    status: ScenarioStatus = ScenarioStatus.DRAFT,
    baseline_start_date: date = date(2026, 9, 1),
    baseline_end_date: date = date(2026, 12, 31),
    created_by: str | None = None,
) -> Scenario:
    """Added Phase 16 — every prior phase's tests built Scenarios only
    through the API; this direct-DB builder is needed for a cross-
    organization IDOR test the same way make_risk/make_stakeholder already
    support theirs (see docs/adr/0016-instance-authorization-completion.md)."""
    scenario = Scenario(
        organization_id=organization.id,
        name=name,
        description=description,
        status=status,
        baseline_start_date=baseline_start_date,
        baseline_end_date=baseline_end_date,
        created_by=created_by,
    )
    session.add(scenario)
    session.flush()
    return scenario

"""Phase 16 audit finding: Phase 12 (docs/adr/0012-organizations-multi-
tenancy.md) hardened every organization-owned repository to require
organization_id and return 404 (never 403) for a cross-organization id —
but only Risk and Stakeholder (Phases 13/14) ever got a DEDICATED
regression test proving it for their own routes. Every entity from Phases
1-12 (Person, Team, TeamMembership, Skill, PersonSkill,
ProjectSkillRequirement, WorkingSchedule, AvailabilityException, Allocation,
Scenario) had zero test anywhere asserting a client in Organization A gets
404, not the other organization's data, when it references an
Organization-B resource id directly. Grepped the entire tests/api/ directory
to confirm before writing this file — see
docs/adr/0016-instance-authorization-completion.md.

This is a test-coverage gap, not a behavior gap: every route below already
resolves its resource through an organization-scoped repository method
(confirmed by reading each service/repository during the Phase 16 audit).
This file proves that holds for real, for every one of these entity types,
in one place — mirroring tests/api/test_risks.py's/test_stakeholders.py's
existing cross-tenancy test pattern exactly. `client` is bound to the
test's default organization (Org A); Org B and everything in it is built
directly via factories, bypassing the API entirely, so this proves the
SERVER-side boundary, not just that the test client never asked for the
wrong org."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import AllocationUnit, AvailabilityType, ScenarioStatus
from tests.factories import (
    make_allocation,
    make_availability_exception,
    make_organization,
    make_person,
    make_person_skill,
    make_project,
    make_project_skill_requirement,
    make_scenario,
    make_skill,
    make_team,
    make_working_schedule,
)


def test_person_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-person")
    person_b = make_person(db_session, organization=org_b, email="org-b-person@example.com")

    assert client.get(f"/api/v1/people/{person_b.id}").status_code == 404
    assert (
        client.patch(f"/api/v1/people/{person_b.id}", json={"first_name": "Changed"}).status_code
        == 404
    )
    assert client.delete(f"/api/v1/people/{person_b.id}").status_code == 404


def test_team_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-team")
    team_b = make_team(db_session, organization=org_b, name="Org B Team")

    assert client.get(f"/api/v1/teams/{team_b.id}").status_code == 404
    assert client.patch(f"/api/v1/teams/{team_b.id}", json={"name": "Renamed"}).status_code == 404
    assert client.get(f"/api/v1/teams/{team_b.id}/members").status_code == 404


def test_team_membership_cannot_be_added_across_organizations(
    client: TestClient, db_session: Session
) -> None:
    """A Person that genuinely exists, but in Org B — Org A's client must
    not be able to add them to an Org A team (the request body's person_id
    is a claim, not proof of tenancy)."""
    org_b = make_organization(db_session, slug="org-b-team-membership")
    person_b = make_person(db_session, organization=org_b, email="org-b-member@example.com")
    team = client.post("/api/v1/teams", json={"name": "Org A Team"}).json()

    response = client.post(
        f"/api/v1/teams/{team['id']}/members", json={"person_id": str(person_b.id)}
    )
    assert response.status_code == 404


def test_skill_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-skill")
    skill_b = make_skill(db_session, organization=org_b, name="Org B Skill")

    assert client.get(f"/api/v1/skills/{skill_b.id}").status_code == 404
    assert (
        client.patch(f"/api/v1/skills/{skill_b.id}", json={"name": "Renamed"}).status_code == 404
    )


def test_person_skill_cannot_reference_a_skill_from_another_organization(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-person-skill")
    skill_b = make_skill(db_session, organization=org_b, name="Org B Skill")
    person = client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex@example.com"},
    ).json()

    response = client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": str(skill_b.id), "proficiency": "proficient"},
    )
    assert response.status_code == 404


def test_person_skill_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-person-skill-2")
    person_b = make_person(db_session, organization=org_b, email="org-b-ps@example.com")
    skill_b = make_skill(db_session, organization=org_b, name="Org B Skill")
    person_skill_b = make_person_skill(
        db_session, organization=org_b, person=person_b, skill=skill_b
    )
    person = client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex2@example.com"},
    ).json()

    # Even referencing OWN org's person_id in the path alongside another
    # org's person_skill_id must not leak that row's data via a 200/other-
    # status side channel.
    assert (
        client.patch(
            f"/api/v1/people/{person['id']}/skills/{person_skill_b.id}",
            json={"proficiency": "expert"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/people/{person['id']}/skills/{person_skill_b.id}"
        ).status_code
        == 404
    )


def test_project_skill_requirement_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-psr")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    skill_b = make_skill(db_session, organization=org_b, name="Org B Skill")
    requirement_b = make_project_skill_requirement(
        db_session, organization=org_b, project=project_b, skill=skill_b
    )

    assert (
        client.get(f"/api/v1/projects/{project_b.id}/skill-requirements").status_code == 404
    )
    assert (
        client.patch(
            f"/api/v1/projects/{project_b.id}/skill-requirements/{requirement_b.id}",
            json={"required_hours": "10"},
        ).status_code
        == 404
    )


def test_working_schedule_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-schedule")
    person_b = make_person(db_session, organization=org_b, email="org-b-schedule@example.com")
    schedule_b = make_working_schedule(db_session, organization=org_b, person=person_b)

    assert client.get(f"/api/v1/working-schedules/{schedule_b.id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/working-schedules/{schedule_b.id}",
            json={"effective_start_date": "2026-01-01"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/working-schedules/{schedule_b.id}").status_code == 404
    # Querying by the OTHER org's person_id: WorkingScheduleService.
    # list_for_person resolves the Person through the org-scoped repository
    # FIRST, so this 404s on the (nonexistent-to-this-org) Person rather
    # than silently returning an empty list — never that org's rows either
    # way.
    listed = client.get(
        "/api/v1/working-schedules", params={"person_id": str(person_b.id)}
    )
    assert listed.status_code == 404


def test_availability_exception_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-availability")
    person_b = make_person(db_session, organization=org_b, email="org-b-avail@example.com")
    exception_b = make_availability_exception(
        db_session,
        organization=org_b,
        person=person_b,
        availability_type=AvailabilityType.ANNUAL_LEAVE,
    )

    assert client.get(f"/api/v1/availability-exceptions/{exception_b.id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/availability-exceptions/{exception_b.id}",
            json={"notes": "changed"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/availability-exceptions/{exception_b.id}").status_code == 404


def test_allocation_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-allocation")
    person_b = make_person(db_session, organization=org_b, email="org-b-alloc@example.com")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    allocation_b = make_allocation(
        db_session,
        organization=org_b,
        person=person_b,
        project=project_b,
        allocation_hours=Decimal("20"),
        allocation_unit=AllocationUnit.TOTAL_HOURS,
    )

    assert client.get(f"/api/v1/allocations/{allocation_b.id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/allocations/{allocation_b.id}", json={"allocation_hours": "10"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/allocations/{allocation_b.id}").status_code == 404


def test_allocation_cannot_be_created_against_a_project_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    """A crafted request body referencing another organization's real
    project_id must not create an allocation against it — confirms the
    organization-scoped ProjectService.get check runs before
    enforce_project_access even has a chance to evaluate a grant."""
    org_b = make_organization(db_session, slug="org-b-allocation-create")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    person = client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex3@example.com"},
    ).json()

    response = client.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"],
            "project_id": str(project_b.id),
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": "20",
        },
    )
    assert response.status_code == 404


def test_scenario_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-scenario")
    scenario_b = make_scenario(
        db_session,
        organization=org_b,
        name="Org B Scenario",
        status=ScenarioStatus.DRAFT,
        baseline_start_date=date(2026, 9, 1),
        baseline_end_date=date(2026, 12, 31),
    )

    assert client.get(f"/api/v1/scenarios/{scenario_b.id}").status_code == 404
    assert (
        client.patch(f"/api/v1/scenarios/{scenario_b.id}", json={"name": "Renamed"}).status_code
        == 404
    )
    assert client.delete(f"/api/v1/scenarios/{scenario_b.id}").status_code == 404
    assert client.get(f"/api/v1/scenarios/{scenario_b.id}/results").status_code == 404
    # The org-scoped list endpoint must never include it either.
    listed = client.get("/api/v1/scenarios").json()
    assert scenario_b.id not in {item["id"] for item in listed["items"]}

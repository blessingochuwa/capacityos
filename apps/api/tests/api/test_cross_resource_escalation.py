"""Phase 16 §13 cross-resource escalation checks — access to one resource
TYPE must never accidentally grant access to a DIFFERENT resource type
unless inheritance is explicitly defined. This file exercises the specific
attack shapes the Phase 16 brief names, and doubles as regression coverage
locking in the Phase 11/16 decisions NOT to build Team→Project inheritance
or Person-level instance scoping (see
docs/adr/0016-instance-authorization-completion.md) — if either of those
were ever added by accident, one of the tests below should start failing.

Team→Team escalation (Manager with Team A access cannot mutate Team B's
members) is already covered by
tests/api/test_team_access_scope.py::test_manager_granted_team_a_still_denied_team_b
and is not duplicated here."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole
from tests.conftest import user_id_of


def _create_project(client: TestClient, name: str = "Website Redesign") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_person(client: TestClient, email: str) -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": email},
    ).json()


def _grant_project_access(owner: TestClient, project_id: object, user_id: str) -> None:
    owner.activate()  # type: ignore[attr-defined]
    response = owner.post(
        f"/api/v1/projects/{project_id}/access-grants", json={"user_id": user_id}
    )
    assert response.status_code == 201, response.text


def test_project_grant_does_not_extend_to_an_unrelated_persons_skills(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """Phase 16 §13 scenario 1 (Manager has Project A access; Person B
    belongs to Project B via an allocation; Manager submits a PersonSkill
    for Person B). PersonSkill is deliberately role-only, not Project- or
    Team-instance-scoped (Phase 11's own documented decision, reaffirmed by
    the Phase 16 audit — Person has no single unambiguous Team/Project
    parent to key scope on). So a Manager holding skill.write (every
    Manager, unconditionally — see ROLE_PERMISSIONS) can mutate ANY
    person's skills in the organization regardless of project grants; this
    is retained, deliberate behavior, not an oversight, and this test
    exists specifically so an accidental future change to that decision
    gets caught here rather than discovered as a real gap."""
    owner = client_as(UserRole.OWNER)
    project_a = _create_project(owner, "Project A")
    project_b = _create_project(owner, "Project B")
    person_b = _create_person(owner, "person-b@example.com")
    owner.activate()  # type: ignore[attr-defined]
    owner.post(
        "/api/v1/allocations",
        json={
            "person_id": person_b["id"],
            "project_id": project_b["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": "20",
        },
    )
    skill_a = owner.post("/api/v1/skills", json={"name": "Backend Development"}).json()
    skill_b = owner.post("/api/v1/skills", json={"name": "Frontend Development"}).json()
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project_a["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/people/{person_b['id']}/skills",
        json={"skill_id": skill_a["id"], "proficiency": "proficient"},
    )
    assert response.status_code == 201

    # Confirms role-based access, not the Project A grant, is what decides
    # this — a Manager without ANY grant reaches the identical outcome.
    stranger_manager = client_as(UserRole.MANAGER)
    stranger_manager.activate()  # type: ignore[attr-defined]
    stranger_response = stranger_manager.post(
        f"/api/v1/people/{person_b['id']}/skills",
        json={"skill_id": skill_b["id"], "proficiency": "proficient"},
    )
    assert stranger_response.status_code == 201


def test_project_grant_does_not_extend_to_an_unrelated_scenario(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """Phase 16 §13 scenario 3 (Manager has Project A access; Manager
    attempts to mutate Scenario B; "must follow Scenario's own
    authorization rules"). Scenario has no Team/Project/Person FK at all
    (docs/adr/0011-instance-level-resource-authorization.md; reaffirmed by
    the Phase 16 audit) — its own rule is role-only: any Manager may
    mutate any Scenario in the organization, independent of every Project
    grant. A grant on Project A neither helps nor is required."""
    owner = client_as(UserRole.OWNER)
    project_a = _create_project(owner, "Project A")
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project_a["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        "/api/v1/scenarios",
        json={
            "name": "Manager's scenario",
            "baseline_start_date": "2026-09-01",
            "baseline_end_date": "2026-12-31",
        },
    )
    assert response.status_code == 201


def test_team_grant_does_not_extend_to_project_mutation(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """The Team→Project inheritance question the Phase 16 brief asks to
    resolve explicitly (§2): a Manager granted access to a Team must not
    thereby gain write access to any Project, since no inheritance was
    implemented (see docs/adr/0016-instance-authorization-completion.md's
    "Team→Project inheritance" decision)."""
    owner = client_as(UserRole.OWNER)
    team = owner.post("/api/v1/teams", json={"name": "Design"}).json()
    project = _create_project(owner, "Unrelated Project")
    manager = client_as(UserRole.MANAGER)
    owner.activate()  # type: ignore[attr-defined]
    grant_response = owner.post(
        f"/api/v1/teams/{team['id']}/access-grants", json={"user_id": user_id_of(manager)}
    )
    assert grant_response.status_code == 201

    manager.activate()  # type: ignore[attr-defined]
    response = manager.patch(f"/api/v1/projects/{project['id']}", json={"name": "Renamed"})
    assert response.status_code == 403

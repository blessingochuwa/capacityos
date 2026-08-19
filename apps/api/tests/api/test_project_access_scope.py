"""Instance-level Project authorization (Phase 11) — mirrors
tests/api/test_team_access_scope.py's structure for Team, covering Project
itself and the nested ProjectSkillRequirement routes (both resolve scope
via the project_id path param). Allocation's body/existing-row-resolved
scope check is covered separately in tests/api/test_allocations.py."""

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole
from tests.conftest import user_id_of


def _create_project(client: TestClient, name: str = "Website Redesign") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_skill(client: TestClient, name: str = "Backend Development") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post("/api/v1/skills", json={"name": name}).json()


def _grant_project_access(owner: TestClient, project_id: object, user_id: str) -> None:
    owner.activate()  # type: ignore[attr-defined]
    response = owner.post(
        f"/api/v1/projects/{project_id}/access-grants", json={"user_id": user_id}
    )
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------------------
# Reads stay global
# ---------------------------------------------------------------------------


def test_manager_can_read_projects_without_any_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    assert manager.get("/api/v1/projects").status_code == 200
    assert manager.get(f"/api/v1/projects/{project['id']}").status_code == 200


# ---------------------------------------------------------------------------
# Manager writes are denied without a grant, allowed with one
# ---------------------------------------------------------------------------


def test_manager_cannot_update_project_without_a_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.patch(f"/api/v1/projects/{project['id']}", json={"name": "Renamed"})
    assert response.status_code == 403


def test_manager_cannot_delete_project_without_a_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    assert manager.delete(f"/api/v1/projects/{project['id']}").status_code == 403


def test_manager_can_update_project_once_granted(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    response = manager.patch(f"/api/v1/projects/{project['id']}", json={"name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


# ---------------------------------------------------------------------------
# Nested ProjectSkillRequirement routes resolve scope via the parent project
# ---------------------------------------------------------------------------


def test_manager_cannot_add_skill_requirement_without_a_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    skill = _create_skill(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": 40},
    )
    assert response.status_code == 403


def test_manager_can_manage_skill_requirements_once_granted(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    skill = _create_skill(owner)
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    create_response = manager.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": 40},
    )
    assert create_response.status_code == 201
    requirement_id = create_response.json()["id"]

    update_response = manager.patch(
        f"/api/v1/projects/{project['id']}/skill-requirements/{requirement_id}",
        json={"required_hours": 50},
    )
    assert update_response.status_code == 200

    delete_response = manager.delete(
        f"/api/v1/projects/{project['id']}/skill-requirements/{requirement_id}"
    )
    assert delete_response.status_code == 204


# ---------------------------------------------------------------------------
# The core IDOR case: granted on Project A, must still be denied on Project B
# ---------------------------------------------------------------------------


def test_manager_granted_project_a_still_denied_project_b(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project_a = _create_project(owner, name="Website Redesign")
    project_b = _create_project(owner, name="Mobile App")
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project_a["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    assert manager.patch(
        f"/api/v1/projects/{project_a['id']}", json={"name": "A Renamed"}
    ).status_code == 200
    assert manager.patch(
        f"/api/v1/projects/{project_b['id']}", json={"name": "B Renamed"}
    ).status_code == 403
    assert manager.delete(f"/api/v1/projects/{project_b['id']}").status_code == 403


# ---------------------------------------------------------------------------
# Revoke takes effect immediately
# ---------------------------------------------------------------------------


def test_revoking_project_access_denies_subsequent_requests(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)
    _grant_project_access(owner, project["id"], manager_id)

    manager.activate()  # type: ignore[attr-defined]
    assert manager.patch(
        f"/api/v1/projects/{project['id']}", json={"name": "First rename"}
    ).status_code == 200

    owner.activate()  # type: ignore[attr-defined]
    revoke_response = owner.delete(f"/api/v1/projects/{project['id']}/access-grants/{manager_id}")
    assert revoke_response.status_code == 204

    manager.activate()  # type: ignore[attr-defined]
    assert manager.patch(
        f"/api/v1/projects/{project['id']}", json={"name": "Second rename"}
    ).status_code == 403


# ---------------------------------------------------------------------------
# Owner/Admin bypass scoping entirely
# ---------------------------------------------------------------------------


def test_owner_and_admin_can_update_any_project_without_a_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    admin = client_as(UserRole.ADMIN)

    owner.activate()  # type: ignore[attr-defined]
    assert owner.patch(
        f"/api/v1/projects/{project['id']}", json={"name": "Owner Renamed"}
    ).status_code == 200

    admin.activate()  # type: ignore[attr-defined]
    assert admin.patch(
        f"/api/v1/projects/{project['id']}", json={"name": "Admin Renamed"}
    ).status_code == 200


def test_admin_can_delete_project_without_a_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    admin = client_as(UserRole.ADMIN)

    admin.activate()  # type: ignore[attr-defined]
    assert admin.delete(f"/api/v1/projects/{project['id']}").status_code == 204


# ---------------------------------------------------------------------------
# 404 for a genuinely nonexistent project, before the scope check even runs
# ---------------------------------------------------------------------------


def test_update_nonexistent_project_returns_404_not_403(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    manager = client_as(UserRole.MANAGER)
    manager.activate()  # type: ignore[attr-defined]
    response = manager.patch(f"/api/v1/projects/{uuid.uuid4()}", json={"name": "Whatever"})
    assert response.status_code == 404

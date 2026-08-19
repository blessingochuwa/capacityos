"""Access-grant management API (Phase 11) — GET/POST/DELETE
/api/v1/{teams,projects}/{id}/access-grants. Gated on Permission.ACCESS_MANAGE,
which only Owner/Admin hold — the central guarantee this file exists to
prove is that a Manager can never grant/revoke access, including to/from
themselves (privilege escalation)."""

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole
from tests.conftest import user_id_of


def _create_team(client: TestClient, name: str = "Design") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post("/api/v1/teams", json={"name": name}).json()


def _create_project(client: TestClient, name: str = "Website Redesign") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post("/api/v1/projects", json={"name": name}).json()


# ---------------------------------------------------------------------------
# Owner/Admin can grant, list, and revoke
# ---------------------------------------------------------------------------


def test_owner_can_grant_list_and_revoke_team_access(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)

    owner.activate()  # type: ignore[attr-defined]
    grant_response = owner.post(
        f"/api/v1/teams/{team['id']}/access-grants", json={"user_id": manager_id}
    )
    assert grant_response.status_code == 201
    assert grant_response.json()["user_id"] == manager_id
    assert grant_response.json()["team_id"] == team["id"]

    list_response = owner.get(f"/api/v1/teams/{team['id']}/access-grants")
    assert list_response.status_code == 200
    assert [g["user_id"] for g in list_response.json()] == [manager_id]

    revoke_response = owner.delete(f"/api/v1/teams/{team['id']}/access-grants/{manager_id}")
    assert revoke_response.status_code == 204
    assert owner.get(f"/api/v1/teams/{team['id']}/access-grants").json() == []


def test_admin_can_grant_and_revoke_project_access(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)
    admin = client_as(UserRole.ADMIN)

    admin.activate()  # type: ignore[attr-defined]
    grant_response = admin.post(
        f"/api/v1/projects/{project['id']}/access-grants", json={"user_id": manager_id}
    )
    assert grant_response.status_code == 201

    revoke_response = admin.delete(
        f"/api/v1/projects/{project['id']}/access-grants/{manager_id}"
    )
    assert revoke_response.status_code == 204


# ---------------------------------------------------------------------------
# Manager (and Member/Viewer) cannot manage access at all
# ---------------------------------------------------------------------------


def test_manager_cannot_grant_team_access_to_anyone(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    other_manager = client_as(UserRole.MANAGER)
    other_manager_id = user_id_of(other_manager)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/teams/{team['id']}/access-grants", json={"user_id": other_manager_id}
    )
    assert response.status_code == 403


def test_manager_cannot_grant_themselves_team_access(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """The core privilege-escalation case: a Manager attempting to grant
    THEMSELVES access to a team they don't manage. Must be denied at the
    permission layer (Permission.ACCESS_MANAGE), and a subsequent write
    attempt by that same Manager must still be denied afterward — proving
    the escalation attempt had no effect end-to-end, not just that the
    grant request itself was rejected."""
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)

    manager.activate()  # type: ignore[attr-defined]
    grant_attempt = manager.post(
        f"/api/v1/teams/{team['id']}/access-grants", json={"user_id": manager_id}
    )
    assert grant_attempt.status_code == 403

    write_attempt = manager.patch(f"/api/v1/teams/{team['id']}", json={"name": "Hijacked"})
    assert write_attempt.status_code == 403


def test_manager_cannot_revoke_a_team_access_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)

    owner.activate()  # type: ignore[attr-defined]
    owner.post(f"/api/v1/teams/{team['id']}/access-grants", json={"user_id": manager_id})

    manager.activate()  # type: ignore[attr-defined]
    response = manager.delete(f"/api/v1/teams/{team['id']}/access-grants/{manager_id}")
    assert response.status_code == 403


def test_viewer_cannot_list_team_access_grants(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    viewer = client_as(UserRole.VIEWER)

    viewer.activate()  # type: ignore[attr-defined]
    assert viewer.get(f"/api/v1/teams/{team['id']}/access-grants").status_code == 403


def test_grant_request_without_authentication_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        f"/api/v1/teams/{uuid.uuid4()}/access-grants", json={"user_id": str(uuid.uuid4())}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Error semantics: 404 for missing team/user, 409 for duplicates
# ---------------------------------------------------------------------------


def test_grant_to_nonexistent_team_returns_404(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)

    owner.activate()  # type: ignore[attr-defined]
    response = owner.post(
        f"/api/v1/teams/{uuid.uuid4()}/access-grants", json={"user_id": manager_id}
    )
    assert response.status_code == 404


def test_grant_to_nonexistent_user_returns_404(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)

    owner.activate()  # type: ignore[attr-defined]
    response = owner.post(
        f"/api/v1/teams/{team['id']}/access-grants", json={"user_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404


def test_duplicate_grant_returns_409(client_as: Callable[[UserRole], TestClient]) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)

    owner.activate()  # type: ignore[attr-defined]
    owner.post(f"/api/v1/teams/{team['id']}/access-grants", json={"user_id": manager_id})
    response = owner.post(
        f"/api/v1/teams/{team['id']}/access-grants", json={"user_id": manager_id}
    )
    assert response.status_code == 409


def test_revoking_a_nonexistent_grant_returns_404(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)

    owner.activate()  # type: ignore[attr-defined]
    response = owner.delete(f"/api/v1/teams/{team['id']}/access-grants/{manager_id}")
    assert response.status_code == 404

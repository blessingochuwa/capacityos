"""Instance-level Team authorization (Phase 11) — a Manager's write/delete
authority on Team/TeamMembership is scoped to teams they've been explicitly
granted, while reads stay global for every role (see
docs/adr/0011-instance-level-resource-authorization.md). Owner/Admin bypass
scoping entirely and must never need a grant row to act.

client_as()-created TestClients all share ONE mutable get_current_user
override on the app object (see tests/conftest.py) — creating a second
client repoints every earlier one too. Tests here that use more than one
role call `<client>.activate()` immediately before every request, rather
than relying on creation order, so the active identity is always explicit.
"""

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole
from tests.conftest import user_id_of


def _create_team(client: TestClient, name: str = "Design") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post("/api/v1/teams", json={"name": name}).json()


def _create_person(client: TestClient, email: str = "alex.morgan@example.com") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": email},
    ).json()


def _grant_team_access(owner: TestClient, team_id: object, user_id: str) -> None:
    owner.activate()  # type: ignore[attr-defined]
    response = owner.post(f"/api/v1/teams/{team_id}/access-grants", json={"user_id": user_id})
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------------------
# Reads stay global — no role needs a grant to view a team
# ---------------------------------------------------------------------------


def test_manager_can_read_teams_without_any_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    assert manager.get("/api/v1/teams").status_code == 200
    assert manager.get(f"/api/v1/teams/{team['id']}").status_code == 200


# ---------------------------------------------------------------------------
# Manager writes are denied without a grant, allowed with one
# ---------------------------------------------------------------------------


def test_manager_cannot_update_team_without_a_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.patch(f"/api/v1/teams/{team['id']}", json={"name": "Renamed"})
    assert response.status_code == 403


def test_manager_cannot_delete_team_without_a_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    assert manager.delete(f"/api/v1/teams/{team['id']}").status_code == 403


def test_manager_cannot_add_or_remove_members_without_a_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    person = _create_person(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]}
    )
    assert response.status_code == 403

    owner.activate()  # type: ignore[attr-defined]
    owner.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})

    manager.activate()  # type: ignore[attr-defined]
    response = manager.delete(f"/api/v1/teams/{team['id']}/members/{person['id']}")
    assert response.status_code == 403


def test_manager_can_update_team_once_granted(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    manager = client_as(UserRole.MANAGER)
    _grant_team_access(owner, team["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    response = manager.patch(f"/api/v1/teams/{team['id']}", json={"name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


# ---------------------------------------------------------------------------
# The core IDOR case: granted on Team A, must still be denied on Team B
# ---------------------------------------------------------------------------


def test_manager_granted_team_a_still_denied_team_b(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team_a = _create_team(owner, name="Design")
    team_b = _create_team(owner, name="Engineering")
    manager = client_as(UserRole.MANAGER)
    _grant_team_access(owner, team_a["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    assert manager.patch(
        f"/api/v1/teams/{team_a['id']}", json={"name": "Design Renamed"}
    ).status_code == 200
    assert manager.patch(
        f"/api/v1/teams/{team_b['id']}", json={"name": "Eng Renamed"}
    ).status_code == 403
    assert manager.delete(f"/api/v1/teams/{team_b['id']}").status_code == 403


# ---------------------------------------------------------------------------
# Revoke takes effect immediately
# ---------------------------------------------------------------------------


def test_revoking_team_access_denies_subsequent_requests(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)
    _grant_team_access(owner, team["id"], manager_id)

    manager.activate()  # type: ignore[attr-defined]
    assert manager.patch(
        f"/api/v1/teams/{team['id']}", json={"name": "First rename"}
    ).status_code == 200

    owner.activate()  # type: ignore[attr-defined]
    revoke_response = owner.delete(f"/api/v1/teams/{team['id']}/access-grants/{manager_id}")
    assert revoke_response.status_code == 204

    manager.activate()  # type: ignore[attr-defined]
    assert manager.patch(
        f"/api/v1/teams/{team['id']}", json={"name": "Second rename"}
    ).status_code == 403


# ---------------------------------------------------------------------------
# Owner/Admin bypass scoping entirely — zero grant rows ever created
# ---------------------------------------------------------------------------


def test_owner_and_admin_can_update_any_team_without_a_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    admin = client_as(UserRole.ADMIN)

    owner.activate()  # type: ignore[attr-defined]
    assert owner.patch(
        f"/api/v1/teams/{team['id']}", json={"name": "Owner Renamed"}
    ).status_code == 200

    admin.activate()  # type: ignore[attr-defined]
    assert admin.patch(
        f"/api/v1/teams/{team['id']}", json={"name": "Admin Renamed"}
    ).status_code == 200


def test_admin_can_delete_team_without_a_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = _create_team(owner)
    admin = client_as(UserRole.ADMIN)

    admin.activate()  # type: ignore[attr-defined]
    assert admin.delete(f"/api/v1/teams/{team['id']}").status_code == 204


# ---------------------------------------------------------------------------
# 404 for a genuinely nonexistent team, before the scope check even runs
# ---------------------------------------------------------------------------


def test_update_nonexistent_team_returns_404_not_403(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    manager = client_as(UserRole.MANAGER)
    manager.activate()  # type: ignore[attr-defined]
    response = manager.patch(f"/api/v1/teams/{uuid.uuid4()}", json={"name": "Whatever"})
    assert response.status_code == 404

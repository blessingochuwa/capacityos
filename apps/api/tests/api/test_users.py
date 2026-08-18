from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole


def _create_user(
    owner: TestClient, *, email: str, role: str = "member"
) -> dict[str, object]:
    response = owner.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": "a reasonably long password",
            "display_name": "Test User",
            "role": role,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_user_never_returns_a_password_field(client: TestClient) -> None:
    body = _create_user(client, email="new@example.com")
    assert "password" not in body
    assert "password_hash" not in body


def test_duplicate_email_returns_409(client: TestClient) -> None:
    _create_user(client, email="dup@example.com")
    response = client.post(
        "/api/v1/users",
        json={
            "email": "dup@example.com",
            "password": "a reasonably long password",
            "display_name": "Another",
            "role": "member",
        },
    )
    assert response.status_code == 409


def test_update_user_display_name(client: TestClient) -> None:
    created = _create_user(client, email="rename@example.com")
    response = client.patch(
        f"/api/v1/users/{created['id']}", json={"display_name": "Renamed"}
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Renamed"


def test_cannot_demote_the_last_remaining_owner(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """conftest's make_test_user creates exactly one Owner per test client;
    demoting it would leave the system with zero active Owners."""
    owner = client_as(UserRole.OWNER)
    me = owner.get("/api/v1/auth/me").json()
    response = owner.patch(f"/api/v1/users/{me['id']}/role", json={"role": "admin"})
    assert response.status_code == 422


def test_cannot_disable_the_last_remaining_owner(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    me = owner.get("/api/v1/auth/me").json()
    response = owner.patch(f"/api/v1/users/{me['id']}", json={"status": "disabled"})
    assert response.status_code == 422


def test_can_demote_an_owner_when_another_owner_still_exists(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    second_owner = _create_user(owner, email="owner2@example.com", role="owner")
    response = owner.patch(
        f"/api/v1/users/{second_owner['id']}/role", json={"role": "admin"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_role_change_produces_an_audit_event_with_old_and_new_role(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    target = _create_user(owner, email="track-role@example.com", role="member")
    owner.patch(f"/api/v1/users/{target['id']}/role", json={"role": "manager"})

    events = owner.get(
        "/api/v1/audit", params={"action": "user.role_change", "resource_type": "user"}
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == target["id"]]
    assert len(matching) == 1
    assert matching[0]["event_metadata"] == {"role_from": "member", "role_to": "manager"}

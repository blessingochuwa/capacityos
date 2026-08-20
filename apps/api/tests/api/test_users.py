from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole


def _create_user(owner: TestClient, *, email: str) -> dict[str, object]:
    """Creates an account only — Phase 12 removed role from UserCreate (see
    app/schemas/user.py). Give the new account a role in an organization
    separately via POST /organizations/{organization_id}/memberships."""
    response = owner.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": "a reasonably long password",
            "display_name": "Test User",
        },
    )
    assert response.status_code == 201
    return response.json()


def _add_membership(
    owner: TestClient, *, organization_id: str, email: str, role: str
) -> dict[str, object]:
    response = owner.post(
        f"/api/v1/organizations/{organization_id}/memberships",
        json={"email": email, "role": role},
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


def test_cannot_demote_the_last_remaining_owner_of_an_organization(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """client_as creates exactly one Owner membership in the test's
    organization; demoting it would leave the organization with zero
    active Owners (Phase 12: this invariant now lives on
    OrganizationMembershipService, scoped per organization)."""
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    user_id = str(owner.user.id)  # type: ignore[attr-defined]
    response = owner.patch(
        f"/api/v1/organizations/{organization_id}/memberships/{user_id}/role",
        json={"role": "admin"},
    )
    assert response.status_code == 422


def test_can_demote_an_owner_when_another_owner_still_exists(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    second_owner_account = _create_user(owner, email="owner2@example.com")
    membership = _add_membership(
        owner, organization_id=organization_id, email="owner2@example.com", role="owner"
    )
    assert membership["user_id"] == second_owner_account["id"]

    response = owner.patch(
        f"/api/v1/organizations/{organization_id}/memberships/{second_owner_account['id']}/role",
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_role_change_produces_an_audit_event_with_old_and_new_role(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    target_account = _create_user(owner, email="track-role@example.com")
    _add_membership(
        owner, organization_id=organization_id, email="track-role@example.com", role="member"
    )
    owner.patch(
        f"/api/v1/organizations/{organization_id}/memberships/{target_account['id']}/role",
        json={"role": "manager"},
    )

    events = owner.get(
        "/api/v1/audit", params={"action": "membership.role_change", "resource_type":
        "organization_membership"},
    ).json()["items"]
    matching = [e for e in events if e["event_metadata"]["user_id"] == target_account["id"]]
    assert len(matching) == 1
    assert matching[0]["event_metadata"] == {
        "user_id": target_account["id"], "role_from": "member", "role_to": "manager"
    }

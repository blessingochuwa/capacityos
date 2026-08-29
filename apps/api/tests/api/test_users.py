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


def test_disabling_a_non_owner_succeeds(client_as: Callable[[UserRole], TestClient]) -> None:
    owner = client_as(UserRole.OWNER)
    target = _create_user(owner, email="non-owner@example.com")
    response = owner.patch(f"/api/v1/users/{target['id']}", json={"status": "disabled"})
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"


def test_cannot_disable_the_last_remaining_owner_of_an_organization(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """Phase 15 closes the Phase 12 gap (ADR 0012's Consequences,
    docs/adr/0015-last-owner-invariant.md): disabling the account of an
    organization's sole active Owner must be rejected exactly like
    demoting or revoking them would be."""
    owner = client_as(UserRole.OWNER)
    user_id = str(owner.user.id)  # type: ignore[attr-defined]
    # A benign read first: client_as's setup rows are only flushed, not
    # committed, until some request on this shared test session actually
    # commits — without this, the failing PATCH below would be the FIRST
    # request, and its rollback would roll back the setup rows themselves,
    # not just the rejected status change.
    assert owner.get(f"/api/v1/users/{user_id}").status_code == 200

    response = owner.patch(f"/api/v1/users/{user_id}", json={"status": "disabled"})
    assert response.status_code == 422
    # And the account must genuinely remain active, not partially disabled.
    refreshed = owner.get(f"/api/v1/users/{user_id}")
    assert refreshed.json()["status"] == "active"


def test_can_disable_an_owner_when_another_owner_still_exists(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    second_owner_account = _create_user(owner, email="owner2@example.com")
    _add_membership(
        owner, organization_id=organization_id, email="owner2@example.com", role="owner"
    )

    response = owner.patch(
        f"/api/v1/users/{second_owner_account['id']}", json={"status": "disabled"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"


def test_cannot_disable_a_user_who_is_the_sole_owner_of_a_second_organization(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """The worked example from the Phase 15 brief: a user who is Owner of
    Org A (via client_as) and additionally the SOLE Owner of Org B (created
    separately) must be blocked from being disabled — the check must cover
    every organization they own, not only the acting one."""
    owner = client_as(UserRole.OWNER)
    user_id = str(owner.user.id)  # type: ignore[attr-defined]
    second_org_response = owner.post(
        "/api/v1/organizations", json={"name": "Second Org", "slug": "second-org"}
    )
    assert second_org_response.status_code == 201

    response = owner.patch(f"/api/v1/users/{user_id}", json={"status": "disabled"})
    assert response.status_code == 422


def test_user_status_change_produces_an_audit_event(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    target = _create_user(owner, email="track-status@example.com")
    response = owner.patch(f"/api/v1/users/{target['id']}", json={"status": "disabled"})
    assert response.status_code == 200

    events = owner.get(
        "/api/v1/audit", params={"action": "user.status_change", "resource_type": "user"}
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == target["id"]]
    assert len(matching) == 1
    assert matching[0]["outcome"] == "success"


def test_list_users_default_returns_the_full_directory(client: TestClient) -> None:
    """Phase 34 baseline: with no `q`/`status`, the directory behaves
    exactly as before — every account is returned. `client` itself creates
    one Owner account; two more are created here."""
    _create_user(client, email="alpha@example.com")
    _create_user(client, email="beta@example.com")

    response = client.get("/api/v1/users")
    assert response.status_code == 200
    body = response.json()
    emails = {item["email"] for item in body["items"]}
    assert {"alpha@example.com", "beta@example.com"}.issubset(emails)
    assert body["total"] >= 3


def test_list_users_search_by_email_substring_is_case_insensitive(
    client: TestClient,
) -> None:
    _create_user(client, email="ada.lovelace@example.com")
    _create_user(client, email="alan.turing@example.com")

    response = client.get("/api/v1/users", params={"q": "LOVELACE"})
    assert response.status_code == 200
    body = response.json()
    assert [item["email"] for item in body["items"]] == ["ada.lovelace@example.com"]
    assert body["total"] == 1


def test_list_users_search_by_display_name_substring(client: TestClient) -> None:
    response_a = client.post(
        "/api/v1/users",
        json={
            "email": "grace@example.com",
            "password": "a reasonably long password",
            "display_name": "Grace Hopper",
        },
    )
    assert response_a.status_code == 201
    _create_user(client, email="someone-else@example.com")

    response = client.get("/api/v1/users", params={"q": "hopper"})
    assert response.status_code == 200
    body = response.json()
    assert [item["display_name"] for item in body["items"]] == ["Grace Hopper"]


def test_list_users_search_with_no_match_returns_an_empty_page(client: TestClient) -> None:
    _create_user(client, email="present@example.com")

    response = client.get("/api/v1/users", params={"q": "nobody-has-this-substring"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_clearing_the_search_restores_the_full_directory(client: TestClient) -> None:
    _create_user(client, email="findme@example.com")

    narrowed = client.get("/api/v1/users", params={"q": "findme"})
    assert narrowed.json()["total"] == 1

    cleared = client.get("/api/v1/users")
    assert cleared.json()["total"] >= 2  # the owner account plus findme@example.com


def test_list_users_filters_by_status(client: TestClient) -> None:
    target = _create_user(client, email="to-disable@example.com")
    client.patch(f"/api/v1/users/{target['id']}", json={"status": "disabled"})
    _create_user(client, email="stays-active@example.com")

    response = client.get("/api/v1/users", params={"status": "disabled"})
    assert response.status_code == 200
    body = response.json()
    emails = {item["email"] for item in body["items"]}
    assert emails == {"to-disable@example.com"}
    assert all(item["status"] == "disabled" for item in body["items"])


def test_list_users_combines_search_and_status_filters(client: TestClient) -> None:
    matching = _create_user(client, email="combo-match@example.com")
    client.patch(f"/api/v1/users/{matching['id']}", json={"status": "disabled"})
    # Same search substring, but still active — must be excluded.
    _create_user(client, email="combo-active@example.com")
    # Disabled, but doesn't match the search substring — must be excluded.
    other = _create_user(client, email="unrelated@example.com")
    client.patch(f"/api/v1/users/{other['id']}", json={"status": "disabled"})

    response = client.get("/api/v1/users", params={"q": "combo", "status": "disabled"})
    assert response.status_code == 200
    body = response.json()
    assert [item["email"] for item in body["items"]] == ["combo-match@example.com"]


def test_list_users_invalid_status_filter_returns_422(client: TestClient) -> None:
    response = client.get("/api/v1/users", params={"status": "not-a-real-status"})
    assert response.status_code == 422


def test_list_users_search_never_exposes_password_fields(client: TestClient) -> None:
    _create_user(client, email="findable@example.com")

    response = client.get("/api/v1/users", params={"q": "findable"})
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert "password" not in item
        assert "password_hash" not in item


def test_manager_cannot_list_users_even_with_search_params(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    manager = client_as(UserRole.MANAGER)
    response = manager.get("/api/v1/users", params={"q": "anything", "status": "active"})
    assert response.status_code == 403


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

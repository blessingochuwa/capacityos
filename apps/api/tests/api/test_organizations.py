"""Organization/membership routes (Phase 12), hardened Phase 15 — this file
covers the last-owner invariant at the HTTP layer for the membership-removal
(revoke) path and sequential multi-owner scenarios. Role-change (demote) API
coverage already lives in tests/api/test_users.py alongside the rest of the
membership-role-change tests it grew up next to; this file adds what wasn't
covered there rather than duplicating it. Multi-ORGANIZATION isolation is
covered at the service layer (tests/services/test_organization_membership.py)
and, for the one path that doesn't require an active-organization switch to
exercise honestly at the API layer, in tests/api/test_users.py's
disable-across-multiple-owned-organizations test. See
docs/adr/0015-last-owner-invariant.md."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole


def _create_user(owner: TestClient, *, email: str) -> dict[str, object]:
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


# ---------------------------------------------------------------------------
# revoke — last-owner invariant
# ---------------------------------------------------------------------------


def test_cannot_revoke_the_last_remaining_owner_of_an_organization(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    user_id = str(owner.user.id)  # type: ignore[attr-defined]
    # Force a commit checkpoint before the failing request — see
    # tests/api/test_users.py's identical comment for why.
    assert owner.get(f"/api/v1/organizations/{organization_id}/memberships").status_code == 200

    response = owner.delete(f"/api/v1/organizations/{organization_id}/memberships/{user_id}")
    assert response.status_code == 422

    memberships = owner.get(f"/api/v1/organizations/{organization_id}/memberships").json()["items"]
    matching = [m for m in memberships if m["user_id"] == user_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "active"


def test_can_revoke_one_of_multiple_owners(client_as: Callable[[UserRole], TestClient]) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    second_owner = _create_user(owner, email="owner2@example.com")
    _add_membership(
        owner, organization_id=organization_id, email="owner2@example.com", role="owner"
    )

    response = owner.delete(
        f"/api/v1/organizations/{organization_id}/memberships/{second_owner['id']}"
    )
    assert response.status_code == 204


def test_revoking_a_non_owner_member_always_succeeds(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    member = _create_user(owner, email="member@example.com")
    _add_membership(
        owner, organization_id=organization_id, email="member@example.com", role="member"
    )

    response = owner.delete(
        f"/api/v1/organizations/{organization_id}/memberships/{member['id']}"
    )
    assert response.status_code == 204


def test_revoke_produces_an_audit_event(client_as: Callable[[UserRole], TestClient]) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    member = _create_user(owner, email="track-revoke@example.com")
    _add_membership(
        owner, organization_id=organization_id, email="track-revoke@example.com", role="member"
    )
    owner.delete(f"/api/v1/organizations/{organization_id}/memberships/{member['id']}")

    events = owner.get(
        "/api/v1/audit",
        params={"action": "membership.revoke", "resource_type": "organization_membership"},
    ).json()["items"]
    assert any(e["resource_id"] == member["id"] for e in events)


# ---------------------------------------------------------------------------
# Sequential multi-owner scenarios (single-process ordering, not concurrency
# — see tests/api/test_last_owner_concurrency.py for genuinely concurrent
# threads against a real file-backed database)
# ---------------------------------------------------------------------------


def test_three_owners_demote_two_sequentially_third_is_blocked(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    owner1_id = str(owner.user.id)  # type: ignore[attr-defined]
    owner2 = _create_user(owner, email="owner2@example.com")
    _add_membership(
        owner, organization_id=organization_id, email="owner2@example.com", role="owner"
    )
    owner3 = _create_user(owner, email="owner3@example.com")
    _add_membership(
        owner, organization_id=organization_id, email="owner3@example.com", role="owner"
    )

    first = owner.patch(
        f"/api/v1/organizations/{organization_id}/memberships/{owner2['id']}/role",
        json={"role": "admin"},
    )
    assert first.status_code == 200
    second = owner.patch(
        f"/api/v1/organizations/{organization_id}/memberships/{owner3['id']}/role",
        json={"role": "admin"},
    )
    assert second.status_code == 200
    third = owner.patch(
        f"/api/v1/organizations/{organization_id}/memberships/{owner1_id}/role",
        json={"role": "admin"},
    )
    assert third.status_code == 422


def test_revoke_then_re_add_an_owner_then_revoke_the_original_succeeds(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """Mirrors the Phase 15 live-verification script: demote isn't the
    only path — add a second Owner, revoke the first (now safe), and
    confirm exactly one Owner remains active throughout."""
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    original_owner_id = str(owner.user.id)  # type: ignore[attr-defined]
    new_owner = _create_user(owner, email="new-owner@example.com")
    _add_membership(
        owner, organization_id=organization_id, email="new-owner@example.com", role="owner"
    )

    response = owner.delete(
        f"/api/v1/organizations/{organization_id}/memberships/{original_owner_id}"
    )
    assert response.status_code == 204

    memberships = owner.get(f"/api/v1/organizations/{organization_id}/memberships").json()["items"]
    active_owners = [
        m for m in memberships if m["role"] == "owner" and m["status"] == "active"
    ]
    assert len(active_owners) == 1
    assert active_owners[0]["user_id"] == new_owner["id"]

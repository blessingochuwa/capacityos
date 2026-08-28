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
docs/adr/0015-last-owner-invariant.md.

Phase 30 added the organization read/rename endpoint coverage at the bottom
of this file — the surface the Organization Settings UI consumes
(docs/adr/0030-organization-settings-ui.md). No production code changed in
Phase 30; these tests document the already-existing PATCH
/api/v1/organizations/{id} contract."""

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


# ---------------------------------------------------------------------------
# Organization read / rename (Phase 12 endpoints; UI surface added Phase 30 —
# docs/adr/0030-organization-settings-ui.md). Deactivation is deliberately
# NOT exercised as a UI-exposed path here: it remains backend-only, and its
# lifecycle (irreversible via the API, denies every member on their next
# request) is unchanged by Phase 30.
# ---------------------------------------------------------------------------


def test_owner_can_read_and_rename_the_active_organization(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]

    before = owner.get(f"/api/v1/organizations/{organization_id}")
    assert before.status_code == 200
    assert before.json()["is_active"] is True
    assert "slug" in before.json()

    renamed = owner.patch(
        f"/api/v1/organizations/{organization_id}", json={"name": "Renamed Org"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed Org"
    # slug is immutable and untouched by a rename
    assert renamed.json()["slug"] == before.json()["slug"]

    after = owner.get(f"/api/v1/organizations/{organization_id}")
    assert after.json()["name"] == "Renamed Org"


def test_rename_rejects_an_empty_name(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    response = owner.patch(
        f"/api/v1/organizations/{organization_id}", json={"name": ""}
    )
    assert response.status_code == 422


def test_rename_produces_an_organization_update_audit_event(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    owner.patch(
        f"/api/v1/organizations/{organization_id}", json={"name": "Audited Rename"}
    )

    events = owner.get(
        "/api/v1/audit",
        params={"action": "organization.update", "resource_type": "organization"},
    ).json()["items"]
    assert any(e["resource_id"] == organization_id for e in events)


def test_non_owner_roles_cannot_rename_the_organization(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """ORGANIZATION_MANAGE is Owner-only (ROLE_PERMISSIONS) — Admin included,
    unlike MEMBERSHIP_MANAGE which Admin does hold."""
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    original_name = owner.get(f"/api/v1/organizations/{organization_id}").json()["name"]

    for role in (UserRole.ADMIN, UserRole.MANAGER, UserRole.MEMBER, UserRole.VIEWER):
        client = client_as(role)
        response = client.patch(
            f"/api/v1/organizations/{organization_id}", json={"name": f"{role.value} tried"}
        )
        assert response.status_code == 403, role

    # nothing was renamed by any of the denied roles
    owner.activate()  # type: ignore[attr-defined]
    assert owner.get(f"/api/v1/organizations/{organization_id}").json()["name"] == original_name


def test_renaming_an_organization_that_is_not_the_active_one_is_not_found(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """_require_active_organization: a path id that isn't the caller's own
    active organization 404s, exactly like a nonexistent one (no IDOR —
    Phase 12)."""
    owner = client_as(UserRole.OWNER)
    response = owner.patch(
        f"/api/v1/organizations/{uuid.uuid4()}", json={"name": "Someone else's org"}
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Deactivation safety guard + reactivation (Phase 31 —
# docs/adr/0031-organization-deactivation-safety.md). The real-login
# lifecycle (deactivate -> every org-scoped route 409 -> reactivate ->
# access restored) and the concurrency guard live in
# tests/api/test_organization_deactivation_safety.py, because client_as
# stubs get_current_membership and so cannot faithfully exercise the
# "inactive org denies the next request" behavior.
# ---------------------------------------------------------------------------


def _second_owner(owner: TestClient, organization_id: str, *, email: str) -> dict[str, object]:
    _create_user(owner, email=email)
    return _add_membership(owner, organization_id=organization_id, email=email, role="owner")


def test_sole_owner_cannot_deactivate_the_organization(
    client_as: Callable[[UserRole], TestClient], db_session: Session
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    # Persist the client_as-created org/membership: the rejected deactivate
    # below raises DomainValidationError, and get_db rolls the request's
    # transaction back — which would also discard the still-uncommitted
    # fixture rows and turn the follow-up GET into a spurious 404. (In
    # production these rows are always already committed.)
    db_session.commit()

    response = owner.post(f"/api/v1/organizations/{organization_id}/deactivate")
    assert response.status_code == 422

    # the guard left the organization untouched
    assert owner.get(f"/api/v1/organizations/{organization_id}").json()["is_active"] is True


def test_owner_can_deactivate_once_a_second_active_owner_exists(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    _second_owner(owner, organization_id, email="co-owner@example.com")

    response = owner.post(f"/api/v1/organizations/{organization_id}/deactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_rejected_deactivation_leaves_memberships_intact_and_no_cascade(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    _create_user(owner, email="member@example.com")
    _add_membership(
        owner, organization_id=organization_id, email="member@example.com", role="member"
    )
    before = owner.get(f"/api/v1/organizations/{organization_id}/memberships").json()["total"]

    assert owner.post(f"/api/v1/organizations/{organization_id}/deactivate").status_code == 422

    after = owner.get(f"/api/v1/organizations/{organization_id}/memberships").json()
    assert after["total"] == before
    assert all(m["status"] == "active" for m in after["items"])


def test_successful_deactivation_only_flips_is_active_no_cascade(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    _second_owner(owner, organization_id, email="co-owner@example.com")
    _create_user(owner, email="member@example.com")
    _add_membership(
        owner, organization_id=organization_id, email="member@example.com", role="member"
    )
    members_before = owner.get(
        f"/api/v1/organizations/{organization_id}/memberships"
    ).json()["items"]

    owner.post(f"/api/v1/organizations/{organization_id}/deactivate")

    members_after = owner.get(
        f"/api/v1/organizations/{organization_id}/memberships"
    ).json()["items"]
    assert {m["user_id"]: m["role"] for m in members_after} == {
        m["user_id"]: m["role"] for m in members_before
    }
    assert all(m["status"] == "active" for m in members_after)


def test_owner_can_reactivate_a_deactivated_organization(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    _second_owner(owner, organization_id, email="co-owner@example.com")
    owner.post(f"/api/v1/organizations/{organization_id}/deactivate")

    response = owner.post(f"/api/v1/organizations/{organization_id}/reactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert response.json()["id"] == organization_id


def test_reactivating_an_already_active_organization_is_an_idempotent_noop(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]

    response = owner.post(f"/api/v1/organizations/{organization_id}/reactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_a_non_owner_member_cannot_reactivate(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    client_as(UserRole.OWNER)  # creates the shared org
    member = client_as(UserRole.MEMBER)
    organization_id = str(member.organization.id)  # type: ignore[attr-defined]

    response = member.post(f"/api/v1/organizations/{organization_id}/reactivate")
    assert response.status_code == 403


def test_reactivating_an_organization_you_are_not_a_member_of_is_not_found(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    response = owner.post(f"/api/v1/organizations/{uuid.uuid4()}/reactivate")
    assert response.status_code == 404


def test_reactivation_produces_an_audit_event(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    organization_id = str(owner.organization.id)  # type: ignore[attr-defined]
    _second_owner(owner, organization_id, email="co-owner@example.com")
    owner.post(f"/api/v1/organizations/{organization_id}/deactivate")
    owner.post(f"/api/v1/organizations/{organization_id}/reactivate")

    events = owner.get(
        "/api/v1/audit",
        params={"action": "organization.reactivate", "resource_type": "organization"},
    ).json()["items"]
    assert any(e["resource_id"] == organization_id for e in events)

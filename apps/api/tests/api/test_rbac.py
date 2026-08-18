"""Permission-boundary tests (Phase 10) — 401 unauthenticated, 403 wrong
role, 2xx correct role, for a representative sample covering every
Permission category. Not exhaustive over all ~70 endpoints (the domain-level
test_authorization.py already proves the full ROLE_PERMISSIONS table is
correct in isolation) — this file proves that table is actually WIRED to
the routes, which is the risk the ADR's threat model calls out (a missing
permission check on a route, not a wrong grant in the table)."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole


def _create_person(owner_client: TestClient, email: str = "alex.morgan@example.com") -> str:
    response = owner_client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": email},
    )
    return response.json()["id"]


# ---------------------------------------------------------------------------
# 401 — no session at all
# ---------------------------------------------------------------------------


def test_list_people_without_authentication_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    assert unauthenticated_client.get("/api/v1/people").status_code == 401


def test_create_person_without_authentication_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex@example.com"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 403 — authenticated, wrong role
# ---------------------------------------------------------------------------


def test_viewer_can_read_people_but_not_create_one(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    viewer = client_as(UserRole.VIEWER)
    assert viewer.get("/api/v1/people").status_code == 200
    response = viewer.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex@example.com"},
    )
    assert response.status_code == 403


def test_viewer_cannot_delete_a_person(client_as: Callable[[UserRole], TestClient]) -> None:
    owner = client_as(UserRole.OWNER)
    person_id = _create_person(owner)
    viewer = client_as(UserRole.VIEWER)
    assert viewer.delete(f"/api/v1/people/{person_id}").status_code == 403


def test_viewer_cannot_use_import(client_as: Callable[[UserRole], TestClient]) -> None:
    viewer = client_as(UserRole.VIEWER)
    response = viewer.post(
        "/api/v1/imports/person/validate",
        files={"file": ("people.csv", b"email,first_name,last_name\n", "text/csv")},
    )
    assert response.status_code == 403


def test_viewer_cannot_export(client_as: Callable[[UserRole], TestClient]) -> None:
    viewer = client_as(UserRole.VIEWER)
    response = viewer.get("/api/v1/exports/person", params={"format": "csv"})
    assert response.status_code == 403


def test_member_can_export_but_not_import(client_as: Callable[[UserRole], TestClient]) -> None:
    member = client_as(UserRole.MEMBER)
    assert member.get("/api/v1/exports/person", params={"format": "csv"}).status_code == 200
    response = member.post(
        "/api/v1/imports/person/validate",
        files={"file": ("people.csv", b"email,first_name,last_name\n", "text/csv")},
    )
    assert response.status_code == 403


def test_manager_can_create_a_person_but_cannot_manage_users(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    manager = client_as(UserRole.MANAGER)
    response = manager.post(
        "/api/v1/people",
        json={"first_name": "Sam", "last_name": "Ade", "email": "sam.ade@example.com"},
    )
    assert response.status_code == 201
    assert manager.get("/api/v1/users").status_code == 403


def test_manager_cannot_read_audit_log(client_as: Callable[[UserRole], TestClient]) -> None:
    manager = client_as(UserRole.MANAGER)
    assert manager.get("/api/v1/audit").status_code == 403


def test_admin_can_manage_users(client_as: Callable[[UserRole], TestClient]) -> None:
    admin = client_as(UserRole.ADMIN)
    response = admin.post(
        "/api/v1/users",
        json={
            "email": "newmember@example.com",
            "password": "a reasonably long password",
            "display_name": "New Member",
            "role": "member",
        },
    )
    assert response.status_code == 201


def test_admin_cannot_promote_a_user_to_admin(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """Only an Owner may grant an Owner/Admin role — see
    docs/adr/0010-authentication-rbac-audit.md."""
    admin = client_as(UserRole.ADMIN)
    created = admin.post(
        "/api/v1/users",
        json={
            "email": "target@example.com",
            "password": "a reasonably long password",
            "display_name": "Target",
            "role": "member",
        },
    ).json()
    response = admin.patch(f"/api/v1/users/{created['id']}/role", json={"role": "admin"})
    assert response.status_code == 403


def test_owner_can_promote_a_user_to_admin(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    created = owner.post(
        "/api/v1/users",
        json={
            "email": "target2@example.com",
            "password": "a reasonably long password",
            "display_name": "Target",
            "role": "member",
        },
    ).json()
    response = owner.patch(f"/api/v1/users/{created['id']}/role", json={"role": "admin"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_admin_can_read_audit_log(client_as: Callable[[UserRole], TestClient]) -> None:
    admin = client_as(UserRole.ADMIN)
    response = admin.get("/api/v1/audit")
    assert response.status_code == 200
    assert "items" in response.json()


# ---------------------------------------------------------------------------
# Every role can read insights/capacity/AI — no role restricts reads
# ---------------------------------------------------------------------------


def test_every_role_can_check_ai_status(client_as: Callable[[UserRole], TestClient]) -> None:
    for role in UserRole:
        response = client_as(role).get("/api/v1/ai/status")
        assert response.status_code == 200, f"{role} should be able to read AI status"

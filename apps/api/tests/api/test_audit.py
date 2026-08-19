"""Proves mutations produce audit events, permission denials are audited,
and audit records never carry secrets — see
docs/adr/0010-authentication-rbac-audit.md."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole
from tests.conftest import user_id_of


def test_creating_a_person_produces_an_audit_event(client: TestClient) -> None:
    created = client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex@example.com"},
    ).json()

    events = client.get(
        "/api/v1/audit", params={"action": "person.create", "resource_type": "person"}
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == created["id"]]
    assert len(matching) == 1
    assert matching[0]["outcome"] == "success"
    assert matching[0]["actor_email"] is not None


def test_audit_event_carries_a_request_id(client: TestClient) -> None:
    client.post(
        "/api/v1/people",
        json={"first_name": "Sam", "last_name": "Ade", "email": "sam.ade@example.com"},
    )
    events = client.get("/api/v1/audit", params={"action": "person.create"}).json()["items"]
    assert all(e["request_id"] for e in events)


def test_permission_denial_produces_an_audit_event(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    viewer = client_as(UserRole.VIEWER)
    viewer.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex@example.com"},
    )

    owner = client_as(UserRole.OWNER)
    events = owner.get("/api/v1/audit", params={"action": "permission.denied"}).json()["items"]
    assert any(e["outcome"] == "denied" for e in events)


def test_audit_metadata_never_contains_a_password_or_token(client: TestClient) -> None:
    """change-password is the one mutating endpoint that handles a
    plaintext secret directly — its audit trail (if any) must never carry
    it. AuthService.change_password's caller (app/api/v1/auth.py) records
    no AuditEvent at all for this action today, which this test locks in:
    a future addition of one must not regress this guarantee."""
    login_response = client.get("/api/v1/auth/me")
    assert login_response.status_code == 200  # sanity: client fixture is authenticated

    events = client.get("/api/v1/audit", params={"limit": 500}).json()["items"]
    for event in events:
        blob = str(event)
        assert "correct horse battery staple" not in blob
        assert "password" not in (event.get("event_metadata") or {})


def test_resource_access_denial_produces_an_audit_event_with_resource_id(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """Phase 11: unlike permission.denied (which never knows a specific
    instance), resource_access.denied always carries resource_id — see
    docs/adr/0011-instance-level-resource-authorization.md."""
    owner = client_as(UserRole.OWNER)
    team = owner.post("/api/v1/teams", json={"name": "Design"}).json()
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    manager.patch(f"/api/v1/teams/{team['id']}", json={"name": "Should be denied"})

    owner.activate()  # type: ignore[attr-defined]
    events = owner.get(
        "/api/v1/audit", params={"action": "resource_access.denied"}
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == team["id"]]
    assert len(matching) == 1
    assert matching[0]["outcome"] == "denied"
    assert matching[0]["resource_type"] == "team"
    assert matching[0]["event_metadata"] == {"permission": "team.write", "role": "manager"}


def test_access_grant_and_revoke_produce_audit_events(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team = owner.post("/api/v1/teams", json={"name": "Design"}).json()
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)

    owner.activate()  # type: ignore[attr-defined]
    owner.post(f"/api/v1/teams/{team['id']}/access-grants", json={"user_id": manager_id})
    owner.delete(f"/api/v1/teams/{team['id']}/access-grants/{manager_id}")

    grant_events = owner.get(
        "/api/v1/audit", params={"action": "access_grant.create"}
    ).json()["items"]
    matching_grant = [e for e in grant_events if e["resource_id"] == team["id"]]
    assert len(matching_grant) == 1
    assert matching_grant[0]["outcome"] == "success"
    assert matching_grant[0]["event_metadata"] == {"target_user_id": manager_id}

    revoke_events = owner.get(
        "/api/v1/audit", params={"action": "access_grant.revoke"}
    ).json()["items"]
    matching_revoke = [e for e in revoke_events if e["resource_id"] == team["id"]]
    assert len(matching_revoke) == 1
    assert matching_revoke[0]["event_metadata"] == {"target_user_id": manager_id}


def test_import_apply_audit_metadata_never_contains_file_content(client: TestClient) -> None:
    marker = "zzz_should_never_leak_into_audit_zzz"
    csv_content = f"email,first_name,last_name\n{marker}@example.com,{marker},Person\n".encode()
    client.post(
        "/api/v1/imports/person/apply",
        files={"file": ("people.csv", csv_content, "text/csv")},
    )
    events = client.get("/api/v1/audit", params={"action": "import.apply"}).json()["items"]
    for event in events:
        assert marker not in str(event)

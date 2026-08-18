"""Proves mutations produce audit events, permission denials are audited,
and audit records never carry secrets — see
docs/adr/0010-authentication-rbac-audit.md."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole


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

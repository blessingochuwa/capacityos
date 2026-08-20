"""Exercises the REAL login/logout/session/CSRF/lockout flow end-to-end,
via unauthenticated_client (no dependency-override shortcut) — see
tests/conftest.py and docs/adr/0010-authentication-rbac-audit.md."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.audit_event import AuditEvent
from app.models.enums import AuditAction, AuditOutcome, MembershipStatus, UserRole, UserStatus
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from tests.factories import make_organization

PASSWORD = "correct horse battery staple"


def _make_user(
    db_session: Session,
    *,
    email: str = "owner@example.com",
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    """A bare account, no organization/role — role is no longer a User
    property (Phase 12). Tests that need permissions/org context use
    _make_user_with_membership below."""
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        display_name="Test User",
        status=status,
    )
    db_session.add(user)
    db_session.flush()
    db_session.commit()
    return user


def _make_user_with_membership(
    db_session: Session, *, email: str = "owner@example.com", role: UserRole = UserRole.OWNER
) -> User:
    """A single active membership means login auto-selects the
    organization (see AuthService.login) — so /auth/me's role/permissions
    are populated with no explicit switch-organization call needed."""
    user = _make_user(db_session, email=email)
    organization = make_organization(db_session)
    db_session.add(
        OrganizationMembership(
            user_id=user.id,
            organization_id=organization.id,
            role=role,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()
    return user


def test_login_with_correct_credentials_returns_200_and_sets_cookies(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    _make_user(db_session)
    response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"
    assert "capacityos_session" in response.cookies
    assert "capacityos_csrf" in response.cookies
    # The session cookie must be httpOnly — not directly assertable from the
    # cookie jar's value, but its Set-Cookie header is.
    set_cookie_headers = response.headers.get_list("set-cookie")
    session_header = next(h for h in set_cookie_headers if h.startswith("capacityos_session="))
    assert "httponly" in session_header.lower()


def test_login_records_an_audit_event(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    user = _make_user(db_session)
    unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    events = db_session.scalars(select(AuditEvent)).all()
    assert any(
        e.action == AuditAction.AUTH_LOGIN_SUCCESS.value
        and e.actor_user_id == user.id
        and e.outcome == AuditOutcome.SUCCESS
        for e in events
    )


def test_login_with_wrong_password_returns_401_with_generic_message(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    _make_user(db_session)
    response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_with_unknown_email_returns_the_identical_message_as_wrong_password(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    """Enumeration resistance — see docs/adr/0010-authentication-rbac-audit.md."""
    _make_user(db_session)
    wrong_password = unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}
    )
    unknown_email = unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_disabled_user_cannot_login_and_gets_the_same_generic_message(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    _make_user(db_session, status=UserStatus.DISABLED)
    response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_account_locks_after_five_failed_attempts(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    user = _make_user(db_session)
    for _ in range(5):
        response = unauthenticated_client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}
        )
        assert response.status_code == 401

    # Even the CORRECT password is now rejected — the account is locked.
    locked_response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert locked_response.status_code == 401
    assert locked_response.json()["detail"] == "Invalid email or password."

    db_session.refresh(user)
    assert user.locked_until is not None

    events = db_session.scalars(select(AuditEvent)).all()
    assert any(e.action == AuditAction.AUTH_ACCOUNT_LOCKED.value for e in events)


def test_successful_login_resets_failed_login_count(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    user = _make_user(db_session)
    for _ in range(3):
        unauthenticated_client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}
        )
    unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    db_session.refresh(user)
    assert user.failed_login_count == 0
    assert user.locked_until is None


def test_me_without_a_session_returns_401(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_a_valid_session_returns_the_current_user(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    _make_user(db_session)
    unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    response = unauthenticated_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"


def test_me_response_includes_the_users_current_permissions(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    """See app/schemas/auth.py::me_to_read — the frontend gates UI
    affordances from this field instead of a second, hand-maintained
    TypeScript copy of the role/permission table. Permissions are relative
    to the caller's active organization (Phase 12) — this user has exactly
    one membership, so login auto-selects it (see AuthService.login)."""
    _make_user_with_membership(
        db_session, email="viewer@example.com", role=UserRole.VIEWER
    )
    unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "viewer@example.com", "password": PASSWORD}
    )
    body = unauthenticated_client.get("/api/v1/auth/me").json()
    assert "person.read" in body["permissions"]
    assert "person.write" not in body["permissions"]


def test_logout_clears_the_session_so_a_subsequent_me_call_returns_401(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    _make_user(db_session)
    unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert unauthenticated_client.get("/api/v1/auth/me").status_code == 200

    logout_response = unauthenticated_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204
    assert unauthenticated_client.get("/api/v1/auth/me").status_code == 401


def test_change_password_without_csrf_header_returns_403(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    _make_user(db_session)
    unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    response = unauthenticated_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a new strong password"},
    )
    assert response.status_code == 403


def test_change_password_with_correct_csrf_header_succeeds_and_new_password_works(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    _make_user(db_session)
    login_response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    csrf_token = login_response.cookies["capacityos_csrf"]

    response = unauthenticated_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a new strong password"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 204

    unauthenticated_client.post("/api/v1/auth/logout")
    relogin = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "a new strong password"},
    )
    assert relogin.status_code == 200


def test_change_password_with_wrong_current_password_returns_403(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    _make_user(db_session)
    login_response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
    )
    csrf_token = login_response.cookies["capacityos_csrf"]

    response = unauthenticated_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "wrong", "new_password": "a new strong password"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 403

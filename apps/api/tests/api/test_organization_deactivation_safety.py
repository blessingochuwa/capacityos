"""Phase 31 — organization deactivation safety guard + reactivation
recovery, at the two levels tests/api/test_organizations.py (which stubs
get_current_membership via client_as) structurally cannot reach:

1. the REAL login/session flow, so the "a deactivated organization denies
   every org-scoped request on the very next call, but reactivation
   still works and restores access" lifecycle is exercised end-to-end
   through the unmodified get_current_membership;
2. genuine CONCURRENCY against a real file-backed SQLite database with
   independent per-thread connections — mirroring
   tests/api/test_last_owner_concurrency.py's Phase 15 precedent exactly
   — so the guard cannot be shown safe only under the in-memory suite's
   single shared connection.

See docs/adr/0031-organization-deactivation-safety.md.
"""

import threading
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.security import hash_password
from app.models.enums import MembershipStatus, UserRole
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.repositories.user import UserRepository
from app.services.organization import OrganizationService
from app.services.organization_membership import OrganizationMembershipService
from tests.factories import make_organization, make_organization_membership, make_user

PASSWORD = "correct horse battery staple"


# ---------------------------------------------------------------------------
# 1. Real login/session lifecycle
# ---------------------------------------------------------------------------


def _owner(db_session: Session, *, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        display_name="Owner",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _login(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return response.cookies["capacityos_csrf"]


def test_full_deactivate_then_reactivate_lifecycle_restores_access(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    organization = make_organization(db_session)
    owner_a = _owner(db_session, email="owner-a@example.com")
    owner_b = _owner(db_session, email="owner-b@example.com")
    for owner in (owner_a, owner_b):
        db_session.add(
            OrganizationMembership(
                user_id=owner.id,
                organization_id=organization.id,
                role=UserRole.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )
    db_session.commit()
    organization_id = str(organization.id)

    csrf = _login(unauthenticated_client, "owner-a@example.com")
    headers = {"X-CSRF-Token": csrf}

    # An org-scoped route works while the organization is active.
    assert unauthenticated_client.get("/api/v1/people").status_code == 200

    deactivate = unauthenticated_client.post(
        f"/api/v1/organizations/{organization_id}/deactivate", headers=headers
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    # Every org-scoped route now 409s — for the acting Owner too — because
    # get_current_membership re-checks organization.is_active per request.
    assert unauthenticated_client.get("/api/v1/people").status_code == 409
    assert (
        unauthenticated_client.get(f"/api/v1/organizations/{organization_id}").status_code == 409
    )
    # ...but the session itself is still valid, and /auth/me now reports
    # the active organization as inactive (Phase 33) without removing the
    # session, role, or permissions — so the frontend can show a global
    # banner and route the Owner to recovery.
    me_inactive = unauthenticated_client.get("/api/v1/auth/me")
    assert me_inactive.status_code == 200
    assert me_inactive.json()["active_organization"]["id"] == organization_id
    assert me_inactive.json()["active_organization"]["is_active"] is False
    assert me_inactive.json()["role"] == "owner"
    assert "organization.manage" in me_inactive.json()["permissions"]

    # Reactivation does not depend on an active-organization context, so
    # the locked-out Owner can still call it.
    reactivate = unauthenticated_client.post(
        f"/api/v1/organizations/{organization_id}/reactivate", headers=headers
    )
    assert reactivate.status_code == 200
    assert reactivate.json()["is_active"] is True
    assert reactivate.json()["id"] == organization_id

    # Access is restored with no re-login, /auth/me reports the org active
    # again (so the frontend banner clears), and every relationship survived.
    assert unauthenticated_client.get("/api/v1/people").status_code == 200
    assert (
        unauthenticated_client.get("/api/v1/auth/me").json()["active_organization"][
            "is_active"
        ]
        is True
    )
    memberships = unauthenticated_client.get(
        f"/api/v1/organizations/{organization_id}/memberships"
    ).json()["items"]
    assert {m["user_id"] for m in memberships} == {str(owner_a.id), str(owner_b.id)}
    assert all(m["status"] == "active" and m["role"] == "owner" for m in memberships)


def test_unauthenticated_reactivation_is_rejected(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    organization = make_organization(db_session)
    db_session.commit()
    response = unauthenticated_client.post(
        f"/api/v1/organizations/{organization.id}/reactivate"
    )
    assert response.status_code == 401


def test_reactivation_requires_a_csrf_token(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    organization = make_organization(db_session)
    owner = _owner(db_session, email="solo-owner@example.com")
    db_session.add(
        OrganizationMembership(
            user_id=owner.id,
            organization_id=organization.id,
            role=UserRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    _login(unauthenticated_client, "solo-owner@example.com")
    response = unauthenticated_client.post(
        f"/api/v1/organizations/{organization.id}/reactivate"
    )
    assert response.status_code == 403


def test_deactivation_requires_a_second_owner_via_the_real_flow(
    unauthenticated_client: TestClient, db_session: Session
) -> None:
    organization = make_organization(db_session)
    owner = _owner(db_session, email="only-owner@example.com")
    db_session.add(
        OrganizationMembership(
            user_id=owner.id,
            organization_id=organization.id,
            role=UserRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()

    csrf = _login(unauthenticated_client, "only-owner@example.com")
    response = unauthenticated_client.post(
        f"/api/v1/organizations/{organization.id}/deactivate",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422
    assert (
        unauthenticated_client.get(f"/api/v1/organizations/{organization.id}").json()[
            "is_active"
        ]
        is True
    )


# ---------------------------------------------------------------------------
# 2. Concurrency — real file-backed SQLite, independent per-thread sessions
# ---------------------------------------------------------------------------


@pytest.fixture
def file_backed_session_factory(tmp_path: Path) -> sessionmaker[Session]:
    """Same shape as tests/api/test_last_owner_concurrency.py's fixture —
    a real file, the default (non-Static) pool, WAL + busy_timeout — so
    genuinely concurrent writers on independent connections are exercised,
    which the in-memory StaticPool suite cannot reproduce."""
    db_path = tmp_path / "phase31_org_deactivation.db"
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _set_pragmas(  # pyright: ignore[reportUnusedFunction]
        dbapi_connection: object, _record: object
    ) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _org_service(session: Session) -> OrganizationService:
    return OrganizationService(
        OrganizationRepository(session), OrganizationMembershipRepository(session)
    )


def _membership_service(session: Session) -> OrganizationMembershipService:
    return OrganizationMembershipService(
        OrganizationMembershipRepository(session), UserRepository(session)
    )


def _two_owner_org(factory: sessionmaker[Session]) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    session = factory()
    organization = make_organization(session)
    owner1 = make_user(session, email="owner1@example.com")
    make_organization_membership(
        session, user=owner1, organization=organization, role=UserRole.OWNER
    )
    owner2 = make_user(session, email="owner2@example.com")
    make_organization_membership(
        session, user=owner2, organization=organization, role=UserRole.OWNER
    )
    session.commit()
    ids = (organization.id, owner1.id, owner2.id)
    session.close()
    return ids


def test_concurrent_deactivate_and_revoke_second_owner_never_strands_the_org(
    file_backed_session_factory: sessionmaker[Session],
) -> None:
    """One request deactivates the org; at the same instant another revokes
    the OTHER Owner's membership. Whatever the interleaving, the
    organization must never end up inactive with zero active Owners — it
    must always remain reactivatable."""
    organization_id, _owner1_id, owner2_id = _two_owner_org(file_backed_session_factory)
    results: dict[str, str] = {}
    lock = threading.Lock()

    def _deactivate() -> None:
        session = file_backed_session_factory()
        try:
            _org_service(session).deactivate(organization_id)
            session.commit()
            outcome = "success"
        except Exception:  # noqa: BLE001 — captured for the assertion
            session.rollback()
            outcome = "blocked"
        finally:
            session.close()
        with lock:
            results["deactivate"] = outcome

    def _revoke_owner2() -> None:
        session = file_backed_session_factory()
        try:
            _membership_service(session).revoke(organization_id, owner2_id)
            session.commit()
            outcome = "success"
        except Exception:  # noqa: BLE001
            session.rollback()
            outcome = "blocked"
        finally:
            session.close()
        with lock:
            results["revoke"] = outcome

    threads = [threading.Thread(target=_deactivate), threading.Thread(target=_revoke_owner2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(t.is_alive() for t in threads), "an operation hung — possible deadlock"

    verify = file_backed_session_factory()
    try:
        owners = OrganizationMembershipRepository(verify).count_active_owners(organization_id)
        assert owners >= 1, "an inactive organization must always keep an Owner who can reactivate"
        organization = OrganizationRepository(verify).get(organization_id)
        assert organization is not None
        if not organization.is_active:
            # recoverable: a remaining Owner reactivates it
            _org_service(verify).reactivate(organization_id)
            verify.commit()
            refreshed = OrganizationRepository(verify).get(organization_id)
            assert refreshed is not None and refreshed.is_active is True
    finally:
        verify.close()


def test_two_concurrent_deactivations_are_safe_and_reversible(
    file_backed_session_factory: sessionmaker[Session],
) -> None:
    organization_id, _owner1_id, _owner2_id = _two_owner_org(file_backed_session_factory)
    errors: list[BaseException] = []

    def _deactivate() -> None:
        session = file_backed_session_factory()
        try:
            _org_service(session).deactivate(organization_id)
            session.commit()
        except BaseException as exc:  # noqa: BLE001 — captured for the assertion
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=_deactivate) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(t.is_alive() for t in threads)
    assert errors == [], (
        f"two concurrent deactivations of a 2-Owner org should both be safe: {errors}"
    )

    verify = file_backed_session_factory()
    try:
        organization = OrganizationRepository(verify).get(organization_id)
        assert organization is not None and organization.is_active is False
        assert OrganizationMembershipRepository(verify).count_active_owners(organization_id) == 2
        _org_service(verify).reactivate(organization_id)
        verify.commit()
        refreshed = OrganizationRepository(verify).get(organization_id)
        assert refreshed is not None and refreshed.is_active is True
    finally:
        verify.close()

"""Last-owner invariant correctness under REAL concurrency (Phase 15) —
against a real file-backed SQLite database with genuinely independent
connections per thread, not the shared in-memory (StaticPool, one shared
connection) fixture used everywhere else in this suite. Mirrors
tests/api/test_access_grant_concurrency.py's Phase 11 precedent exactly:
that suite is what first caught a real cross-connection SQLite deadlock the
in-memory suite structurally cannot reproduce (see
docs/adr/0010-authentication-rbac-audit.md), so Phase 15 repeats that
pattern for its own genuinely concurrent write path rather than trusting the
in-memory suite to prove it.

The race this file targets: an organization has exactly two active Owners.
Two concurrent requests each attempt to remove ONE of them (by role change,
revoke, or account deactivation). A naive "read the owner count, then
decide, then write" implementation lets both requests observe count=2 and
both proceed, leaving zero Owners. See
app/repositories/organization_membership.py::change_role_if_safe/
revoke_if_safe and app/repositories/user.py::disable_if_safe's docstrings
for the atomic-guarded-UPDATE mechanism this file verifies actually holds
under real contention, and docs/adr/0015-last-owner-invariant.md for the
full concurrency writeup, including what SQLite's locking model can and
cannot prove here (single-machine, single-file serialization — not a
PostgreSQL-grade guarantee, and not claimed as one)."""

import threading
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.enums import UserRole, UserStatus
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.repositories.user import UserRepository
from app.services.organization_membership import OrganizationMembershipService
from app.services.user import UserService
from tests.factories import make_organization, make_organization_membership, make_user


@pytest.fixture
def file_backed_session_factory(tmp_path: Path) -> sessionmaker[Session]:
    """A real file, the default (non-Static) connection pool, and the same
    WAL/busy_timeout PRAGMAs app/core/database.py sets for real deployments
    — see tests/api/test_access_grant_concurrency.py's identical fixture
    for the full rationale; duplicated here rather than shared because
    tmp_path is per-test and pytest fixtures don't compose across modules
    without a conftest change this phase doesn't otherwise need."""
    db_path = tmp_path / "phase15_last_owner_concurrency.db"
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


def _membership_service(session: Session) -> OrganizationMembershipService:
    return OrganizationMembershipService(
        OrganizationMembershipRepository(session), UserRepository(session)
    )


def _user_service(session: Session) -> UserService:
    from app.repositories.person import PersonRepository

    return UserService(UserRepository(session), PersonRepository(session))


def test_two_concurrent_demotes_of_the_last_two_owners_yield_exactly_one_survivor(
    file_backed_session_factory: sessionmaker[Session],
) -> None:
    """The canonical race from the Phase 15 brief: exactly 2 active Owners,
    both demoted at the same instant. Exactly one must succeed (whichever
    commits first); the other must be rejected once it re-evaluates the
    guard against the first one's already-committed change — never both
    succeeding, which would leave zero Owners."""
    setup_session = file_backed_session_factory()
    organization = make_organization(setup_session)
    owner1 = make_user(setup_session, email="owner1@example.com")
    owner1_membership = make_organization_membership(
        setup_session, user=owner1, organization=organization, role=UserRole.OWNER
    )
    owner2 = make_user(setup_session, email="owner2@example.com")
    owner2_membership = make_organization_membership(
        setup_session, user=owner2, organization=organization, role=UserRole.OWNER
    )
    setup_session.commit()
    organization_id, owner1_id, owner2_id = organization.id, owner1.id, owner2.id
    owner1_membership_id, owner2_membership_id = owner1_membership.id, owner2_membership.id
    setup_session.close()

    results: dict[str, str] = {}
    lock = threading.Lock()

    def _demote(label: str, user_id: uuid.UUID, membership_id: uuid.UUID) -> None:
        session = file_backed_session_factory()
        try:
            # A fresh session's own OrganizationMembership object standing
            # in for what get_current_membership would resolve per-request
            # in production — only its .role is read by the escalation
            # check, so a lightweight re-fetch is faithful enough here.
            acting_membership = OrganizationMembershipRepository(session).get(membership_id)
            assert acting_membership is not None
            _membership_service(session).change_role(
                organization_id, user_id, UserRole.ADMIN, acting_membership=acting_membership
            )
            session.commit()
            outcome = "success"
        except Exception:  # noqa: BLE001 — captured for the assertion below
            session.rollback()
            outcome = "blocked"
        finally:
            session.close()
        with lock:
            results[label] = outcome

    threads = [
        threading.Thread(target=_demote, args=("owner1", owner1_id, owner1_membership_id)),
        threading.Thread(target=_demote, args=("owner2", owner2_id, owner2_membership_id)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(t.is_alive() for t in threads), "a demote hung — possible deadlock"
    assert sorted(results.values()) == ["blocked", "success"], (
        f"expected exactly one winner and one invariant-blocked loser, got {results}"
    )

    verify_session = file_backed_session_factory()
    try:
        remaining = OrganizationMembershipRepository(verify_session).count_active_owners(
            organization_id
        )
        assert remaining == 1, "the organization must never end up with zero active Owners"
    finally:
        verify_session.close()


def test_concurrent_demote_and_revoke_of_the_last_two_owners_yield_exactly_one_survivor(
    file_backed_session_factory: sessionmaker[Session],
) -> None:
    """Same race, different mutation TYPES on each side — one request
    demotes Owner1's role, the other revokes Owner2's membership entirely,
    at the same instant. The invariant must hold regardless of which two
    owner-removing operation types collide."""
    setup_session = file_backed_session_factory()
    organization = make_organization(setup_session)
    owner1 = make_user(setup_session, email="owner1@example.com")
    owner1_membership = make_organization_membership(
        setup_session, user=owner1, organization=organization, role=UserRole.OWNER
    )
    owner2 = make_user(setup_session, email="owner2@example.com")
    make_organization_membership(
        setup_session, user=owner2, organization=organization, role=UserRole.OWNER
    )
    setup_session.commit()
    organization_id, owner1_id, owner2_id = organization.id, owner1.id, owner2.id
    owner1_membership_id = owner1_membership.id
    setup_session.close()

    results: dict[str, str] = {}
    lock = threading.Lock()

    def _demote_owner1() -> None:
        session = file_backed_session_factory()
        try:
            acting_membership = OrganizationMembershipRepository(session).get(owner1_membership_id)
            assert acting_membership is not None
            _membership_service(session).change_role(
                organization_id, owner1_id, UserRole.ADMIN, acting_membership=acting_membership
            )
            session.commit()
            outcome = "success"
        except Exception:  # noqa: BLE001
            session.rollback()
            outcome = "blocked"
        finally:
            session.close()
        with lock:
            results["demote_owner1"] = outcome

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
            results["revoke_owner2"] = outcome

    threads = [threading.Thread(target=_demote_owner1), threading.Thread(target=_revoke_owner2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(t.is_alive() for t in threads), "an operation hung — possible deadlock"
    assert sorted(results.values()) == ["blocked", "success"], (
        f"expected exactly one winner, got {results}"
    )

    verify_session = file_backed_session_factory()
    try:
        assert (
            OrganizationMembershipRepository(verify_session).count_active_owners(organization_id)
            == 1
        )
    finally:
        verify_session.close()


def test_concurrent_disable_and_demote_of_the_last_two_owners_yield_exactly_one_survivor(
    file_backed_session_factory: sessionmaker[Session],
) -> None:
    """The account-deactivation path (Section 4C) races against a
    membership-role-change on the OTHER owner — a mutation on a different
    table entirely (users vs organization_memberships), which is exactly
    why UserRepository.disable_if_safe embeds its own guard rather than
    delegating to OrganizationMembershipRepository's."""
    setup_session = file_backed_session_factory()
    organization = make_organization(setup_session)
    owner1 = make_user(setup_session, email="owner1@example.com")
    owner1_membership = make_organization_membership(
        setup_session, user=owner1, organization=organization, role=UserRole.OWNER
    )
    owner2 = make_user(setup_session, email="owner2@example.com")
    make_organization_membership(
        setup_session, user=owner2, organization=organization, role=UserRole.OWNER
    )
    setup_session.commit()
    organization_id, owner1_id, owner2_id = organization.id, owner1.id, owner2.id
    owner1_membership_id = owner1_membership.id
    setup_session.close()

    results: dict[str, str] = {}
    lock = threading.Lock()

    def _demote_owner1() -> None:
        session = file_backed_session_factory()
        try:
            acting_membership = OrganizationMembershipRepository(session).get(owner1_membership_id)
            assert acting_membership is not None
            _membership_service(session).change_role(
                organization_id, owner1_id, UserRole.ADMIN, acting_membership=acting_membership
            )
            session.commit()
            outcome = "success"
        except Exception:  # noqa: BLE001
            session.rollback()
            outcome = "blocked"
        finally:
            session.close()
        with lock:
            results["demote_owner1"] = outcome

    def _disable_owner2() -> None:
        session = file_backed_session_factory()
        try:
            from app.schemas.user import UserUpdate

            _user_service(session).update(
                organization_id, owner2_id, UserUpdate(status=UserStatus.DISABLED)
            )
            session.commit()
            outcome = "success"
        except Exception:  # noqa: BLE001
            session.rollback()
            outcome = "blocked"
        finally:
            session.close()
        with lock:
            results["disable_owner2"] = outcome

    threads = [threading.Thread(target=_demote_owner1), threading.Thread(target=_disable_owner2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(t.is_alive() for t in threads), "an operation hung — possible deadlock"
    assert sorted(results.values()) == ["blocked", "success"], (
        f"expected exactly one winner, got {results}"
    )

    verify_session = file_backed_session_factory()
    try:
        assert (
            OrganizationMembershipRepository(verify_session).count_active_owners(organization_id)
            == 1
        )
    finally:
        verify_session.close()


def test_concurrent_demotes_for_different_organizations_both_succeed(
    file_backed_session_factory: sessionmaker[Session],
) -> None:
    """Sanity check mirroring test_access_grant_concurrency.py's identical
    check — busy_timeout serializing genuinely concurrent writers must not
    spuriously fail an operation that was never actually racing another
    for the SAME organization's Owner count."""
    setup_session = file_backed_session_factory()
    org_a = make_organization(setup_session, name="Org A")
    org_b = make_organization(setup_session, name="Org B")
    owner_a = make_user(setup_session, email="owner-a@example.com")
    owner_a_membership = make_organization_membership(
        setup_session, user=owner_a, organization=org_a, role=UserRole.OWNER
    )
    co_owner_a = make_user(setup_session, email="co-owner-a@example.com")
    make_organization_membership(
        setup_session, user=co_owner_a, organization=org_a, role=UserRole.OWNER
    )
    owner_b = make_user(setup_session, email="owner-b@example.com")
    owner_b_membership = make_organization_membership(
        setup_session, user=owner_b, organization=org_b, role=UserRole.OWNER
    )
    co_owner_b = make_user(setup_session, email="co-owner-b@example.com")
    make_organization_membership(
        setup_session, user=co_owner_b, organization=org_b, role=UserRole.OWNER
    )
    setup_session.commit()
    org_a_id, owner_a_id, owner_a_membership_id = org_a.id, owner_a.id, owner_a_membership.id
    org_b_id, owner_b_id, owner_b_membership_id = org_b.id, owner_b.id, owner_b_membership.id
    setup_session.close()

    errors: list[BaseException] = []

    def _demote(organization_id: uuid.UUID, user_id: uuid.UUID, membership_id: uuid.UUID) -> None:
        session = file_backed_session_factory()
        try:
            acting_membership = OrganizationMembershipRepository(session).get(membership_id)
            assert acting_membership is not None
            _membership_service(session).change_role(
                organization_id, user_id, UserRole.ADMIN, acting_membership=acting_membership
            )
            session.commit()
        except BaseException as exc:  # noqa: BLE001 — captured for the assertion below
            errors.append(exc)
        finally:
            session.close()

    threads = [
        threading.Thread(target=_demote, args=(org_a_id, owner_a_id, owner_a_membership_id)),
        threading.Thread(target=_demote, args=(org_b_id, owner_b_id, owner_b_membership_id)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == [], f"neither org had a real Owner-count conflict: {errors}"
    verify_session = file_backed_session_factory()
    try:
        repo = OrganizationMembershipRepository(verify_session)
        assert repo.count_active_owners(org_a_id) == 1
        assert repo.count_active_owners(org_b_id) == 1
    finally:
        verify_session.close()

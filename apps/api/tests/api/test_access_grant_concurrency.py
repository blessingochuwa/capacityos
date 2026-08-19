"""Grant/revoke correctness against a REAL file-backed SQLite database, not
the shared in-memory (StaticPool, one shared connection) test fixture used
everywhere else in this suite.

Phase 10 shipped two real bugs the in-memory suite never caught — a Decimal
precision regression, and a cross-connection SQLite deadlock — both only
reproducible against a genuine file with genuinely independent connections
(see docs/adr/0010-authentication-rbac-audit.md and
app/core/database.py's WAL/busy_timeout PRAGMA comment). Phase 11's
grant/revoke mutations get the same treatment here rather than repeating
that mistake.
"""

import threading
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.exceptions import ConflictError
from app.repositories.project import ProjectRepository
from app.repositories.project_access_grant import ProjectAccessGrantRepository
from app.repositories.team import TeamRepository
from app.repositories.team_access_grant import TeamAccessGrantRepository
from app.repositories.user import UserRepository
from app.services.access_grant import AccessGrantService
from tests.factories import make_team, make_user


@pytest.fixture
def file_backed_session_factory(tmp_path: Path) -> sessionmaker[Session]:
    """A real file, the default (non-Static) connection pool, and the same
    WAL/busy_timeout PRAGMAs app/core/database.py sets for real deployments
    — so independent threads get independent connections that can actually
    contend with each other, unlike the shared in-memory db_session
    fixture."""
    db_path = tmp_path / "phase11_concurrency.db"
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


def _service_for(session: Session) -> AccessGrantService:
    return AccessGrantService(
        TeamAccessGrantRepository(session),
        ProjectAccessGrantRepository(session),
        UserRepository(session),
        TeamRepository(session),
        ProjectRepository(session),
    )


def test_concurrent_duplicate_grant_attempts_yield_exactly_one_winner(
    file_backed_session_factory: sessionmaker[Session],
) -> None:
    setup_session = file_backed_session_factory()
    admin = make_user(setup_session)
    manager = make_user(setup_session, email="manager@example.com")
    team = make_team(setup_session)
    setup_session.commit()
    team_id, manager_id, admin_id = team.id, manager.id, admin.id
    setup_session.close()

    results: list[str] = []
    lock = threading.Lock()

    def _attempt_grant() -> None:
        session = file_backed_session_factory()
        try:
            service = _service_for(session)
            admin_ref = UserRepository(session).get(admin_id)
            assert admin_ref is not None
            service.grant_team_access(team_id, manager_id, granted_by=admin_ref)
            session.commit()
            outcome = "success"
        except (ConflictError, IntegrityError):
            session.rollback()
            outcome = "conflict"
        finally:
            session.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=_attempt_grant) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(results) == 8, "every thread must complete without hanging or raising unexpectedly"
    assert results.count("success") == 1, f"expected exactly one winner, got {results}"
    assert results.count("conflict") == 7

    verify_session = file_backed_session_factory()
    try:
        grants = TeamAccessGrantRepository(verify_session).list_for_team(team_id)
        assert len(grants) == 1, "no duplicate row should exist after concurrent contention"
    finally:
        verify_session.close()


def test_grant_revoke_grant_sequence_across_independent_connections(
    file_backed_session_factory: sessionmaker[Session],
) -> None:
    """Each step below uses its OWN session/connection (never sharing one
    across steps) — proving the sequence doesn't deadlock against a real
    file, which the Phase 10 bug (a second connection blocking against the
    first's open transaction) shows is not guaranteed for free."""
    setup_session = file_backed_session_factory()
    admin = make_user(setup_session)
    manager = make_user(setup_session, email="manager@example.com")
    team = make_team(setup_session)
    setup_session.commit()
    admin_id, manager_id, team_id = admin.id, manager.id, team.id
    setup_session.close()

    def _grant() -> None:
        session = file_backed_session_factory()
        try:
            admin_ref = UserRepository(session).get(admin_id)
            assert admin_ref is not None
            _service_for(session).grant_team_access(team_id, manager_id, granted_by=admin_ref)
            session.commit()
        finally:
            session.close()

    def _revoke() -> None:
        session = file_backed_session_factory()
        try:
            _service_for(session).revoke_team_access(team_id, manager_id)
            session.commit()
        finally:
            session.close()

    def _exists() -> bool:
        session = file_backed_session_factory()
        try:
            return TeamAccessGrantRepository(session).exists(manager_id, team_id)
        finally:
            session.close()

    for step in (_grant, _revoke, _grant):
        thread = threading.Thread(target=step)
        thread.start()
        thread.join(timeout=10)
        assert not thread.is_alive(), "operation hung — possible cross-connection deadlock"

    assert _exists() is True


def test_concurrent_grants_for_different_teams_both_succeed(
    file_backed_session_factory: sessionmaker[Session],
) -> None:
    """Sanity check that WAL mode's busy_timeout serializes genuinely
    concurrent writers rather than one spuriously failing — two DIFFERENT
    (user, team) pairs granted at the same time must both succeed, not
    just the duplicate-contention case above."""
    setup_session = file_backed_session_factory()
    admin = make_user(setup_session)
    manager = make_user(setup_session, email="manager@example.com")
    team_a = make_team(setup_session, name="Team A")
    team_b = make_team(setup_session, name="Team B")
    setup_session.commit()
    admin_id, manager_id = admin.id, manager.id
    team_a_id, team_b_id = team_a.id, team_b.id
    setup_session.close()

    errors: list[BaseException] = []

    def _grant(team_id: uuid.UUID) -> None:
        session = file_backed_session_factory()
        try:
            admin_ref = UserRepository(session).get(admin_id)
            assert admin_ref is not None
            _service_for(session).grant_team_access(team_id, manager_id, granted_by=admin_ref)
            session.commit()
        except BaseException as exc:  # noqa: BLE001 — captured for the assertion below
            errors.append(exc)
        finally:
            session.close()

    threads = [
        threading.Thread(target=_grant, args=(team_a_id,)),
        threading.Thread(target=_grant, args=(team_b_id,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == [], f"both grants should succeed without contention: {errors}"
    verify_session = file_backed_session_factory()
    try:
        assert TeamAccessGrantRepository(verify_session).exists(manager_id, team_a_id) is True
        assert TeamAccessGrantRepository(verify_session).exists(manager_id, team_b_id) is True
    finally:
        verify_session.close()

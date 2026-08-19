import uuid
from collections.abc import Callable, Generator
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Registers all models on Base.metadata before create_all() is called below.
import app.models  # noqa: F401  # pyright: ignore[reportUnusedImport]
from app.api.deps import get_current_user, require_csrf
from app.core.database import Base, get_db
from app.main import app
from app.models.enums import UserRole, UserStatus
from app.models.user import User


@pytest.fixture
def db_session() -> Generator[Session]:
    """A fresh in-memory SQLite database per test.

    Deliberately not the Alembic migration path — that's exercised manually
    (see docs/adr/0002-phase-1-domain-foundation.md) and would make every
    test slower and dependent on migration state. Base.metadata.create_all
    builds the identical schema from the same model definitions, so table/
    column/constraint shape is still exercised; only the migration file
    itself is untested here.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _get_db_override(db_session: Session) -> Callable[[], Generator[Session]]:
    def _override() -> Generator[Session]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    return _override


def make_test_user(
    session: Session, role: UserRole = UserRole.OWNER, *, email: str | None = None
) -> User:
    """A persisted User row for dependency-override-based test
    authentication (see `client`/`client_as` below) — this bypasses
    get_current_user entirely rather than going through AuthService.login,
    so password_hash is a placeholder no login attempt ever verifies
    against. It exists purely to give routes/AuditService a real
    User.id/.email/.role to work with. Real login-flow behavior (password
    verification, cookies, lockout, CSRF) is exercised separately via
    `unauthenticated_client` and a genuine POST /api/v1/auth/login — see
    tests/api/test_auth.py."""
    user = User(
        email=email or f"test-{role.value}-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="!unused! — see make_test_user docstring",
        display_name=f"Test {role.value.title()}",
        role=role,
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.flush()
    return user


def user_id_of(client: TestClient) -> str:
    """The string id of a client_as()-created TestClient's underlying
    User — Phase 11 tests that grant/revoke instance-level access need
    this. `client.user` is a dynamic attribute (see client_as's `_make`
    below), which plain `# type: ignore[attr-defined]` comments at call
    sites don't reliably narrow back to `str` everywhere they're used —
    this helper's explicit `-> str` return annotation is the one place
    that conversion is declared, so every call site gets a real `str`
    without repeating the workaround."""
    return str(client.user.id)  # type: ignore[attr-defined]


@pytest.fixture
def unauthenticated_client(db_session: Session) -> Generator[TestClient]:
    """A TestClient with no auth bypass at all — DB wiring only. Used to
    exercise the real login/logout/session/CSRF flow end-to-end (Phase 10),
    where a dependency-override shortcut would defeat the point of the
    test."""
    app.dependency_overrides[get_db] = _get_db_override(db_session)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client_as(db_session: Session) -> Generator[Callable[[UserRole], TestClient]]:
    """Factory for a TestClient pre-authenticated as a given role, bypassing
    the real login flow via FastAPI dependency overrides (Phase 10) — the
    same pattern this fixture module already used for get_db, extended to
    get_current_user/require_csrf. CSRF is bypassed here by design: CSRF
    has its own dedicated real-login-flow test (see
    tests/api/test_auth.py), and re-deriving a CSRF token for every one of
    this suite's hundreds of pre-existing mutation tests would test
    plumbing, not behavior. Every pre-Phase-10 test keeps using the plain
    `client` fixture below (always Owner) — new Phase 10 RBAC tests use
    this factory to exercise other roles."""
    app.dependency_overrides[get_db] = _get_db_override(db_session)
    app.dependency_overrides[require_csrf] = lambda: None
    stack = ExitStack()

    def _make(role: UserRole) -> TestClient:
        user = make_test_user(db_session, role)

        def _activate() -> None:
            app.dependency_overrides[get_current_user] = lambda: user

        _activate()
        test_client = stack.enter_context(TestClient(app))
        test_client.user = user  # type: ignore[attr-defined]
        # Phase 11 tests that need to grant/revoke instance-level access for
        # THIS specific test client's user (e.g. "grant this Manager access
        # to Team A") need its real User.id, which client_as's Callable
        # signature otherwise has no way to expose — attaching it here
        # keeps every pre-Phase-11 call site (which only uses the returned
        # TestClient) unchanged.
        #
        # get_current_user is overridden via ONE shared mutable slot on the
        # `app` object, not per-client state — so creating a second client
        # via client_as() silently repoints EVERY previously-returned
        # TestClient at the new identity too (they all read
        # app.dependency_overrides dynamically per request). Multi-actor
        # Phase 11 tests (owner grants access, then the manager acts, then
        # the owner revokes it, then the manager acts again) need to switch
        # back to an earlier client's identity without minting a brand-new
        # user each time — test_client.activate() does exactly that.
        test_client.activate = _activate  # type: ignore[attr-defined]
        return test_client

    try:
        yield _make
    finally:
        stack.close()
        app.dependency_overrides.clear()


@pytest.fixture
def client(client_as: Callable[[UserRole], TestClient]) -> TestClient:
    """The default authenticated client used by every pre-Phase-10 test —
    always an Owner (the superset-permission role), so none of those tests
    needed to change: this fixture's only job before Phase 10 was DB
    wiring, and it still is, from every existing test's perspective."""
    return client_as(UserRole.OWNER)

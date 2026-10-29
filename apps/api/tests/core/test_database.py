"""create_database_engine (Phase 53A.1): stale pooled connections are
detected and replaced (pool_pre_ping), and the existing SQLite behavior is
unchanged.

These tests use a file-backed SQLite database, where a "stale" connection is
simulated by closing the pooled connection's underlying DBAPI connection
behind the pool's back. That exercises SQLAlchemy's pre-ping/invalidate/
reconnect path deterministically, but it is NOT proof of recovery from a
real PostgreSQL connection dropped by Neon's scale-to-zero — that must be
verified against the deployed database (docs/production-readiness.md,
"Prototype deployment")."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import DBAPIError

from app.core import database
from app.core.database import create_database_engine


def _sqlite_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'capacityos-test.db'}"


def _count_new_connections(engine: Engine) -> list[int]:
    connects = [0]

    @event.listens_for(engine, "connect")
    def _on_connect(  # pyright: ignore[reportUnusedFunction]
        _dbapi_connection: object, _connection_record: object
    ) -> None:
        connects[0] += 1

    return connects


def _leave_a_dead_connection_in_the_pool(engine: Engine) -> None:
    """Checks a connection out, returns it to the pool normally, then closes
    its DBAPI connection — so the pool now holds a connection that looks
    idle-but-usable and is actually dead, the state Neon's suspend leaves
    behind."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        dbapi_connection = connection.connection.dbapi_connection
    assert dbapi_connection is not None
    dbapi_connection.close()


def test_a_dead_pooled_connection_is_replaced_transparently(tmp_path: Path) -> None:
    engine = create_database_engine(_sqlite_url(tmp_path))
    try:
        connects = _count_new_connections(engine)
        _leave_a_dead_connection_in_the_pool(engine)

        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1

        assert connects[0] == 2  # the original, plus one replacement
    finally:
        engine.dispose()


def test_without_pre_ping_the_same_dead_connection_fails(tmp_path: Path) -> None:
    """Control: proves the test above exercises pre-ping, not some other
    recovery path — an engine built without it hands out the dead
    connection and the query fails."""
    engine = create_engine(_sqlite_url(tmp_path))
    try:
        _leave_a_dead_connection_in_the_pool(engine)

        with pytest.raises(DBAPIError), engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def test_a_healthy_pooled_connection_is_reused_not_reopened(tmp_path: Path) -> None:
    """Pre-ping adds one cheap round trip per checkout; it must not open a
    new connection when the pooled one is fine."""
    engine = create_database_engine(_sqlite_url(tmp_path))
    try:
        connects = _count_new_connections(engine)
        for _ in range(3):
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        assert connects[0] == 1
    finally:
        engine.dispose()


def test_sqlite_pragmas_are_still_applied(tmp_path: Path) -> None:
    engine = create_database_engine(_sqlite_url(tmp_path))
    try:
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
            assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
    finally:
        engine.dispose()


def test_the_application_engine_has_pre_ping_enabled() -> None:
    """The module-level engine is bound to the configured DATABASE_URL, so
    connecting to it here is not safe. SQLAlchemy exposes no public getter
    for the pre_ping flag, so this reads Pool._pre_ping (set from
    create_engine's pool_pre_ping argument) as the least-invasive check that
    the app engine itself, not just the factory, has it."""
    assert database.engine.pool._pre_ping is True  # pyright: ignore[reportPrivateUsage]

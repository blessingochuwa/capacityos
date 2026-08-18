from collections.abc import Generator
from typing import Any

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)

if settings.database_url.startswith("sqlite"):
    # WAL mode lets one writer proceed concurrently with readers on OTHER
    # connections — SQLite's default rollback-journal mode does not, and a
    # second connection's write can raise "database is locked" while a
    # first connection still holds an open (even read-only) transaction.
    # This became a real, observed failure in Phase 10: AuditService
    # (app/api/deps.py::get_audit_service) deliberately writes through a
    # SECOND connection, independent of the request-scoped `db` connection
    # every other repository/service uses (see that module's docstring for
    # why) — against a file-backed database, that is two connections in
    # the same request. busy_timeout is a defensive second layer: a brief
    # wait-and-retry at the SQLite level before raising, rather than
    # failing immediately on any residual contention. Both PRAGMAs are
    # silently no-ops on `:memory:` (this codebase's test database — see
    # tests/conftest.py) — SQLite always uses its own in-memory journal
    # there regardless of what journal_mode is requested — so this changes
    # no test behavior, only real file-backed dev/production databases.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(  # pyright: ignore[reportUnusedFunction]
        dbapi_connection: Any, _connection_record: object
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Standard Alembic-recommended naming convention: gives every constraint a
# deterministic name. Without this, SQLite and PostgreSQL each auto-name
# unnamed constraints (ForeignKey, PrimaryKey, unnamed UniqueConstraint)
# differently and non-reproducibly, which breaks Alembic's ability to
# reference them in a future migration (e.g. to drop/alter one). There is no
# "ck" entry: every CheckConstraint in this codebase is already given an
# explicit, table-scoped name in the model (e.g. ck_project_end_after_start)
# — a "ck" convention would wrap that name a second time (SQLAlchemy treats
# an explicit CheckConstraint name as the convention's %(constraint_name)s
# token and re-applies the template), producing redundant names like
# ck_projects_ck_project_end_after_start.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def get_db() -> Generator[Session]:
    """Request-scoped session with request-scoped transaction semantics:
    commit once at the end of a successful request, roll back on any
    exception (including domain exceptions like NotFoundError raised by a
    service mid-request), always close. Routes/services never call
    commit()/rollback() themselves — repositories only flush() so
    constraint violations surface immediately without ending the
    transaction early.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

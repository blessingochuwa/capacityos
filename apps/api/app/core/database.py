from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
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

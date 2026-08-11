from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Registers all models on Base.metadata before create_all() is called below.
import app.models  # noqa: F401  # pyright: ignore[reportUnusedImport]
from app.core.database import Base, get_db
from app.main import app


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


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient]:
    """A TestClient sharing db_session for the whole test, so the test can
    both drive the API and inspect resulting DB state directly."""

    def _get_db_override() -> Generator[Session]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = _get_db_override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()

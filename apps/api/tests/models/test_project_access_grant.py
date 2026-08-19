import pytest
from sqlalchemy import create_engine, delete, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.project import Project
from app.models.user import User
from app.repositories.project_access_grant import ProjectAccessGrantRepository
from tests.factories import make_project, make_project_access_grant, make_user


def test_create_project_access_grant(db_session: Session) -> None:
    user = make_user(db_session)
    project = make_project(db_session)
    grant = make_project_access_grant(db_session, user=user, project=project)

    assert grant.id is not None
    assert grant.user_id == user.id
    assert grant.project_id == project.id
    assert grant.granted_by_user_id is None


def test_grant_records_who_granted_it(db_session: Session) -> None:
    admin = make_user(db_session, email="admin@example.com")
    manager = make_user(db_session, email="manager@example.com")
    project = make_project(db_session)
    grant = make_project_access_grant(db_session, user=manager, project=project, granted_by=admin)

    assert grant.granted_by_user_id == admin.id


def test_duplicate_project_access_grant_is_rejected(db_session: Session) -> None:
    user = make_user(db_session)
    project = make_project(db_session)
    make_project_access_grant(db_session, user=user, project=project)

    with pytest.raises(IntegrityError):
        make_project_access_grant(db_session, user=user, project=project)


def test_same_user_can_be_granted_multiple_projects(db_session: Session) -> None:
    user = make_user(db_session)
    website = make_project(db_session, name="Website Redesign")
    mobile = make_project(db_session, name="Mobile App")
    make_project_access_grant(db_session, user=user, project=website)
    make_project_access_grant(db_session, user=user, project=mobile)

    repository = ProjectAccessGrantRepository(db_session)
    assert len(repository.list_for_user(user.id)) == 2


def _fk_enforced_session() -> Session:
    """See tests/models/test_team_access_grant.py::_fk_enforced_session for
    why this dedicated engine exists rather than using the shared db_session
    fixture — SQLite's default-off FK enforcement is a pre-existing,
    codebase-wide characteristic, not a Phase 11 gap."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_fk(  # pyright: ignore[reportUnusedFunction]
        dbapi_connection: object, _record: object
    ) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def test_deleting_user_cascades_to_project_access_grant_with_fk_enforcement() -> None:
    session = _fk_enforced_session()
    user = make_user(session)
    project = make_project(session)
    make_project_access_grant(session, user=user, project=project)

    session.execute(delete(User).where(User.id == user.id))
    session.flush()

    assert ProjectAccessGrantRepository(session).list_for_project(project.id) == []


def test_deleting_project_cascades_to_project_access_grant_with_fk_enforcement() -> None:
    session = _fk_enforced_session()
    user = make_user(session)
    project = make_project(session)
    make_project_access_grant(session, user=user, project=project)

    session.execute(delete(Project).where(Project.id == project.id))
    session.flush()

    assert ProjectAccessGrantRepository(session).list_for_user(user.id) == []


def test_repository_exists_and_get_by_user_and_project(db_session: Session) -> None:
    user = make_user(db_session)
    granted_project = make_project(db_session, name="Website Redesign")
    ungranted_project = make_project(db_session, name="Mobile App")
    make_project_access_grant(db_session, user=user, project=granted_project)

    repository = ProjectAccessGrantRepository(db_session)
    assert repository.exists(user.id, granted_project.id) is True
    assert repository.exists(user.id, ungranted_project.id) is False
    assert repository.get_by_user_and_project(user.id, granted_project.id) is not None
    assert repository.get_by_user_and_project(user.id, ungranted_project.id) is None

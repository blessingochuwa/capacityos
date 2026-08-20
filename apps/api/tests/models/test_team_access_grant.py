import pytest
from sqlalchemy import create_engine, delete, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.organization import Organization
from app.models.team import Team
from app.models.user import User
from app.repositories.team_access_grant import TeamAccessGrantRepository
from tests.factories import make_organization, make_team, make_team_access_grant, make_user


def test_create_team_access_grant(db_session: Session, organization: Organization) -> None:
    user = make_user(db_session)
    team = make_team(db_session, organization=organization)
    grant = make_team_access_grant(db_session, organization=organization, user=user, team=team)

    assert grant.id is not None
    assert grant.user_id == user.id
    assert grant.team_id == team.id
    assert grant.granted_by_user_id is None


def test_grant_records_who_granted_it(db_session: Session, organization: Organization) -> None:
    admin = make_user(db_session, email="admin@example.com")
    manager = make_user(db_session, email="manager@example.com")
    team = make_team(db_session, organization=organization)
    grant = make_team_access_grant(
        db_session, organization=organization, user=manager, team=team, granted_by=admin
    )

    assert grant.granted_by_user_id == admin.id


def test_duplicate_team_access_grant_is_rejected(
    db_session: Session, organization: Organization
) -> None:
    user = make_user(db_session)
    team = make_team(db_session, organization=organization)
    make_team_access_grant(db_session, organization=organization, user=user, team=team)

    with pytest.raises(IntegrityError):
        make_team_access_grant(db_session, organization=organization, user=user, team=team)


def test_same_user_can_be_granted_multiple_teams(
    db_session: Session, organization: Organization
) -> None:
    user = make_user(db_session)
    design = make_team(db_session, organization=organization, name="Design")
    engineering = make_team(db_session, organization=organization, name="Engineering")
    make_team_access_grant(db_session, organization=organization, user=user, team=design)
    make_team_access_grant(db_session, organization=organization, user=user, team=engineering)

    repository = TeamAccessGrantRepository(db_session)
    assert len(repository.list_for_user(user.id, organization.id)) == 2


def _fk_enforced_session() -> Session:
    """SQLite defaults `PRAGMA foreign_keys` to OFF (verified: neither
    app/core/database.py nor the shared db_session fixture enables it — a
    pre-existing characteristic of this codebase, not a Phase 11 gap), so
    the ondelete="CASCADE" declared on TeamAccessGrant's FKs never actually
    fires against the shared in-memory test fixture. It DOES fire in real
    PostgreSQL (FK enforcement is always on there), which is what this
    constraint is actually for. This dedicated engine turns the pragma on
    explicitly so the CASCADE DDL itself is verified, without changing the
    shared fixture's behavior for every other test in the suite."""
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


def test_deleting_user_cascades_to_team_access_grant_with_fk_enforcement() -> None:
    session = _fk_enforced_session()
    organization = make_organization(session)
    user = make_user(session)
    team = make_team(session, organization=organization)
    make_team_access_grant(session, organization=organization, user=user, team=team)

    session.execute(delete(User).where(User.id == user.id))
    session.flush()

    assert TeamAccessGrantRepository(session).list_for_team(team.id, organization.id) == []


def test_deleting_team_cascades_to_team_access_grant_with_fk_enforcement() -> None:
    session = _fk_enforced_session()
    organization = make_organization(session)
    user = make_user(session)
    team = make_team(session, organization=organization)
    make_team_access_grant(session, organization=organization, user=user, team=team)

    session.execute(delete(Team).where(Team.id == team.id))
    session.flush()

    assert TeamAccessGrantRepository(session).list_for_user(user.id, organization.id) == []


def test_repository_exists_and_get_by_user_and_team(
    db_session: Session, organization: Organization
) -> None:
    user = make_user(db_session)
    granted_team = make_team(db_session, organization=organization, name="Design")
    ungranted_team = make_team(db_session, organization=organization, name="Engineering")
    make_team_access_grant(db_session, organization=organization, user=user, team=granted_team)

    repository = TeamAccessGrantRepository(db_session)
    assert repository.exists(user.id, granted_team.id, organization.id) is True
    assert repository.exists(user.id, ungranted_team.id, organization.id) is False
    assert repository.get_by_user_and_team(user.id, granted_team.id, organization.id) is not None
    assert repository.get_by_user_and_team(user.id, ungranted_team.id, organization.id) is None

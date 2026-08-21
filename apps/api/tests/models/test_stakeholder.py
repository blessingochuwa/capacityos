import pytest
from sqlalchemy import create_engine, delete, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.enums import (
    StakeholderDecisionAuthority,
    StakeholderInfluence,
    StakeholderInterest,
)
from app.models.organization import Organization
from app.models.person import Person
from app.models.project import Project
from app.repositories.stakeholder import StakeholderRepository
from tests.factories import make_organization, make_person, make_project, make_stakeholder


def test_create_stakeholder_with_defaults(db_session: Session, organization: Organization) -> None:
    project = make_project(db_session, organization=organization)
    stakeholder = make_stakeholder(db_session, organization=organization, project=project)

    assert stakeholder.id is not None
    assert stakeholder.project_id == project.id
    assert stakeholder.organization_id == organization.id
    assert stakeholder.influence == StakeholderInfluence.MEDIUM
    assert stakeholder.interest == StakeholderInterest.MEDIUM
    assert stakeholder.decision_authority == StakeholderDecisionAuthority.INFORMED
    assert stakeholder.person_id is None


def test_create_stakeholder_with_full_fields(
    db_session: Session, organization: Organization
) -> None:
    project = make_project(db_session, organization=organization)
    person = make_person(db_session, organization=organization)
    stakeholder = make_stakeholder(
        db_session,
        organization=organization,
        project=project,
        name="Alex Morgan",
        person=person,
        role="Product Owner",
        influence=StakeholderInfluence.HIGH,
        interest=StakeholderInterest.HIGH,
        decision_authority=StakeholderDecisionAuthority.DECISION_MAKER,
        communication_needs="Weekly steering committee update",
    )

    assert stakeholder.person_id == person.id
    assert stakeholder.role == "Product Owner"
    assert stakeholder.decision_authority == StakeholderDecisionAuthority.DECISION_MAKER
    assert stakeholder.communication_needs == "Weekly steering committee update"


def test_duplicate_person_on_same_project_is_rejected(
    db_session: Session, organization: Organization
) -> None:
    project = make_project(db_session, organization=organization)
    person = make_person(db_session, organization=organization)
    make_stakeholder(db_session, organization=organization, project=project, person=person)

    with pytest.raises(IntegrityError):
        make_stakeholder(db_session, organization=organization, project=project, person=person)


def test_same_person_can_be_a_stakeholder_on_multiple_projects(
    db_session: Session, organization: Organization
) -> None:
    person = make_person(db_session, organization=organization)
    project_a = make_project(db_session, organization=organization, name="Project A")
    project_b = make_project(db_session, organization=organization, name="Project B")
    make_stakeholder(db_session, organization=organization, project=project_a, person=person)
    make_stakeholder(db_session, organization=organization, project=project_b, person=person)

    repository = StakeholderRepository(db_session)
    assert len(repository.list_for_project(project_a.id, organization.id)) == 1
    assert len(repository.list_for_project(project_b.id, organization.id)) == 1


def test_multiple_external_stakeholders_with_no_person_are_allowed(
    db_session: Session, organization: Organization
) -> None:
    """person_id NULL doesn't collide under the composite unique
    constraint — matches Project.external_id's precedent (see
    docs/adr/0012-organizations-multi-tenancy.md)."""
    project = make_project(db_session, organization=organization)
    make_stakeholder(db_session, organization=organization, project=project, name="Client A")
    make_stakeholder(db_session, organization=organization, project=project, name="Client B")

    repository = StakeholderRepository(db_session)
    assert len(repository.list_for_project(project.id, organization.id)) == 2


def _fk_enforced_session() -> Session:
    """See tests/models/test_project_access_grant.py::_fk_enforced_session
    for why this dedicated engine exists rather than the shared db_session
    fixture — SQLite's default-off FK enforcement is a pre-existing,
    codebase-wide characteristic, not a Phase 14 gap."""
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


def test_deleting_project_cascades_to_its_stakeholders_with_fk_enforcement() -> None:
    session = _fk_enforced_session()
    organization = make_organization(session)
    project = make_project(session, organization=organization)
    make_stakeholder(session, organization=organization, project=project)

    session.execute(delete(Project).where(Project.id == project.id))
    session.flush()

    assert StakeholderRepository(session).list_for_project(project.id, organization.id) == []


def test_deleting_linked_person_sets_stakeholder_person_to_null_with_fk_enforcement() -> None:
    """SET NULL, not CASCADE — the stakeholder record outlives whichever
    person it happens to be linked to (see Stakeholder.person_id's
    docstring)."""
    session = _fk_enforced_session()
    organization = make_organization(session)
    project = make_project(session, organization=organization)
    person = make_person(session, organization=organization)
    stakeholder = make_stakeholder(
        session, organization=organization, project=project, person=person
    )

    session.execute(delete(Person).where(Person.id == person.id))
    session.flush()
    session.refresh(stakeholder)

    assert stakeholder.person_id is None
    assert StakeholderRepository(session).get(stakeholder.id, organization.id) is not None

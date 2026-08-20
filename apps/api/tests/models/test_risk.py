from datetime import date

from sqlalchemy import create_engine, delete, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.enums import RiskImpact, RiskProbability, RiskStatus
from app.models.organization import Organization
from app.models.person import Person
from app.models.project import Project
from app.repositories.risk import RiskRepository
from tests.factories import make_organization, make_person, make_project, make_risk


def test_create_risk_with_defaults(db_session: Session, organization: Organization) -> None:
    project = make_project(db_session, organization=organization)
    risk = make_risk(db_session, organization=organization, project=project)

    assert risk.id is not None
    assert risk.project_id == project.id
    assert risk.organization_id == organization.id
    assert risk.probability == RiskProbability.MEDIUM
    assert risk.impact == RiskImpact.MEDIUM
    assert risk.status == RiskStatus.OPEN
    assert risk.owner_person_id is None
    assert risk.review_date is None


def test_create_risk_with_full_fields(db_session: Session, organization: Organization) -> None:
    project = make_project(db_session, organization=organization)
    owner = make_person(db_session, organization=organization)
    risk = make_risk(
        db_session,
        organization=organization,
        project=project,
        description="Vendor may miss the delivery deadline",
        cause="Vendor has a history of delays",
        potential_effect="Project launch slips by 2 weeks",
        probability=RiskProbability.HIGH,
        impact=RiskImpact.HIGH,
        response="Weekly check-ins with the vendor",
        owner=owner,
        status=RiskStatus.MITIGATING,
        review_date=date(2026, 9, 1),
    )

    assert risk.owner_person_id == owner.id
    assert risk.status == RiskStatus.MITIGATING
    assert risk.review_date == date(2026, 9, 1)


def _fk_enforced_session() -> Session:
    """See tests/models/test_project_access_grant.py::_fk_enforced_session
    for why this dedicated engine exists rather than the shared db_session
    fixture — SQLite's default-off FK enforcement is a pre-existing,
    codebase-wide characteristic, not a Phase 13 gap."""
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


def test_deleting_project_cascades_to_its_risks_with_fk_enforcement() -> None:
    session = _fk_enforced_session()
    organization = make_organization(session)
    project = make_project(session, organization=organization)
    make_risk(session, organization=organization, project=project)

    session.execute(delete(Project).where(Project.id == project.id))
    session.flush()

    assert RiskRepository(session).list_for_project(project.id, organization.id) == []


def test_deleting_owner_person_sets_risk_owner_to_null_with_fk_enforcement() -> None:
    """SET NULL, not CASCADE — the risk record outlives whichever person
    currently owns it (see Risk.owner_person_id's docstring)."""
    session = _fk_enforced_session()
    organization = make_organization(session)
    project = make_project(session, organization=organization)
    owner = make_person(session, organization=organization)
    risk = make_risk(session, organization=organization, project=project, owner=owner)

    session.execute(delete(Person).where(Person.id == owner.id))
    session.flush()
    session.refresh(risk)

    assert risk.owner_person_id is None
    assert RiskRepository(session).get(risk.id, organization.id) is not None

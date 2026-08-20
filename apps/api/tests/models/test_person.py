import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import EmploymentStatus
from app.models.organization import Organization
from tests.factories import make_organization, make_person


def test_create_valid_person(db_session: Session, organization: Organization) -> None:
    person = make_person(db_session, organization=organization)
    assert person.id is not None
    assert person.display_name == "Alex Morgan"
    assert person.employment_status is EmploymentStatus.ACTIVE
    assert person.created_at is not None
    assert person.updated_at is not None


def test_display_name_can_be_overridden(db_session: Session, organization: Organization) -> None:
    person = make_person(
        db_session, organization=organization, first_name="Sam", last_name="Ade",
        display_name="Sami",
    )
    assert person.display_name == "Sami"


def test_email_must_be_unique(db_session: Session, organization: Organization) -> None:
    make_person(db_session, organization=organization, email="dup@example.com")
    with pytest.raises(IntegrityError):
        make_person(db_session, organization=organization, email="dup@example.com")


def test_email_can_repeat_across_organizations(db_session: Session) -> None:
    """Phase 12: Person.email uniqueness is scoped to (organization_id,
    email), not globally unique — two different organizations may each
    have their own person at the same email address."""
    org_a = make_organization(db_session, slug="org-a")
    org_b = make_organization(db_session, slug="org-b")
    make_person(db_session, organization=org_a, email="shared@example.com")
    make_person(db_session, organization=org_b, email="shared@example.com")


def test_employment_status_check_constraint_rejects_arbitrary_value(
    db_session: Session, organization: Organization
) -> None:
    """Proves EmploymentStatus is enforced at the DB level, not just in
    application code — bypass the ORM's own enum validation with a raw
    UPDATE to hit the CHECK constraint directly."""
    person = make_person(db_session, organization=organization)
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.execute(
            text("UPDATE people SET employment_status = 'bogus' WHERE id = :id"),
            {"id": person.id.hex},
        )
        db_session.flush()

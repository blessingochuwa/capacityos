import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import EmploymentStatus
from tests.factories import make_person


def test_create_valid_person(db_session: Session) -> None:
    person = make_person(db_session)
    assert person.id is not None
    assert person.display_name == "Alex Morgan"
    assert person.employment_status is EmploymentStatus.ACTIVE
    assert person.created_at is not None
    assert person.updated_at is not None


def test_display_name_can_be_overridden(db_session: Session) -> None:
    person = make_person(db_session, first_name="Sam", last_name="Ade", display_name="Sami")
    assert person.display_name == "Sami"


def test_email_must_be_unique(db_session: Session) -> None:
    make_person(db_session, email="dup@example.com")
    with pytest.raises(IntegrityError):
        make_person(db_session, email="dup@example.com")


def test_employment_status_check_constraint_rejects_arbitrary_value(db_session: Session) -> None:
    """Proves EmploymentStatus is enforced at the DB level, not just in
    application code — bypass the ORM's own enum validation with a raw
    UPDATE to hit the CHECK constraint directly."""
    person = make_person(db_session)
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.execute(
            text("UPDATE people SET employment_status = 'bogus' WHERE id = :id"),
            {"id": person.id.hex},
        )
        db_session.flush()

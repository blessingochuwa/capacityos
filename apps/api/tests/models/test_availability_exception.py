from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import AvailabilityType
from tests.factories import make_availability_exception, make_person


def test_create_fully_unavailable_exception(db_session: Session) -> None:
    """hours=None means fully unavailable for the whole period — the common
    case (annual leave, sick leave)."""
    person = make_person(db_session)
    exception = make_availability_exception(db_session, person=person)

    assert exception.hours is None
    assert exception.availability_type is AvailabilityType.ANNUAL_LEAVE


def test_create_partially_available_exception(db_session: Session) -> None:
    """hours=4 means the person is available 4 hours/day during the period
    (e.g. normally works 8 hours/day, reduced to 4 for this period)."""
    person = make_person(db_session)
    exception = make_availability_exception(
        db_session,
        person=person,
        availability_type=AvailabilityType.REDUCED_AVAILABILITY,
        hours=Decimal("4"),
    )

    assert exception.hours == Decimal("4")


def test_end_date_before_start_date_is_rejected(db_session: Session) -> None:
    person = make_person(db_session)
    with pytest.raises(IntegrityError):
        make_availability_exception(
            db_session, person=person, start_date=date(2026, 9, 19), end_date=date(2026, 9, 15)
        )


def test_negative_hours_is_rejected(db_session: Session) -> None:
    person = make_person(db_session)
    with pytest.raises(IntegrityError):
        make_availability_exception(db_session, person=person, hours=Decimal("-1"))


def test_availability_type_has_no_db_check_constraint(db_session: Session) -> None:
    """Deliberate design: unlike EmploymentStatus/ProjectStatus/
    AllocationUnit, AvailabilityType is NOT DB-constrained (see
    AvailabilityException model docstring and ADR 0002) — an arbitrary
    string is accepted at the database level so new reasons never require a
    migration. Application-level validation (Pydantic) is what keeps normal
    usage to the controlled vocabulary."""
    person = make_person(db_session)
    exception = make_availability_exception(db_session, person=person)
    db_session.commit()

    db_session.execute(
        text(
            "UPDATE availability_exceptions SET availability_type = 'not_a_real_reason' "
            "WHERE id = :id"
        ),
        {"id": exception.id.hex},
    )
    db_session.flush()  # does not raise — proves there is no CHECK constraint

    stored_value = db_session.scalar(
        text("SELECT availability_type FROM availability_exceptions WHERE id = :id"),
        {"id": exception.id.hex},
    )
    assert stored_value == "not_a_real_reason"  # confirms the UPDATE actually took effect

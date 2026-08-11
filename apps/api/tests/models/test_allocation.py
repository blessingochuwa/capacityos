from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import make_allocation, make_person, make_project


def test_create_valid_allocation(db_session: Session) -> None:
    person = make_person(db_session)
    project = make_project(db_session)
    allocation = make_allocation(db_session, person=person, project=project)

    assert allocation.id is not None
    assert allocation.person is person
    assert allocation.project is project
    assert allocation.allocation_hours == Decimal("20")


def test_end_date_before_start_date_is_rejected(db_session: Session) -> None:
    person = make_person(db_session)
    project = make_project(db_session)
    with pytest.raises(IntegrityError):
        make_allocation(
            db_session,
            person=person,
            project=project,
            start_date=date(2026, 9, 30),
            end_date=date(2026, 9, 1),
        )


def test_negative_allocation_hours_is_rejected(db_session: Session) -> None:
    person = make_person(db_session)
    project = make_project(db_session)
    with pytest.raises(IntegrityError):
        make_allocation(db_session, person=person, project=project, allocation_hours=Decimal("-1"))


def test_zero_allocation_hours_is_valid(db_session: Session) -> None:
    person = make_person(db_session)
    project = make_project(db_session)
    allocation = make_allocation(
        db_session, person=person, project=project, allocation_hours=Decimal("0")
    )
    assert allocation.allocation_hours == Decimal("0")


def test_deleting_project_cascades_to_allocations(db_session: Session) -> None:
    person = make_person(db_session)
    project = make_project(db_session)
    make_allocation(db_session, person=person, project=project)

    db_session.delete(project)
    db_session.flush()

    assert person.allocations == []

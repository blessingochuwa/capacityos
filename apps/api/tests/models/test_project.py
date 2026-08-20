from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import ProjectStatus
from app.models.organization import Organization
from tests.factories import make_project


def test_create_valid_project(db_session: Session, organization: Organization) -> None:
    project = make_project(db_session, organization=organization)
    assert project.id is not None
    assert project.status is ProjectStatus.PLANNED


def test_project_without_dates_is_valid(db_session: Session, organization: Organization) -> None:
    project = make_project(db_session, organization=organization, start_date=None, end_date=None)
    assert project.start_date is None
    assert project.end_date is None


def test_end_date_before_start_date_is_rejected(
    db_session: Session, organization: Organization
) -> None:
    with pytest.raises(IntegrityError):
        make_project(
            db_session,
            organization=organization,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 9, 1),
        )


def test_end_date_equal_to_start_date_is_valid(
    db_session: Session, organization: Organization
) -> None:
    project = make_project(
        db_session,
        organization=organization,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 1),
    )
    assert project.start_date == project.end_date

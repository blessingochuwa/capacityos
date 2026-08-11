from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.working_schedule import WorkingScheduleEntry
from tests.factories import make_person, make_working_schedule


def test_create_valid_five_day_schedule(db_session: Session) -> None:
    person = make_person(db_session)
    schedule = make_working_schedule(db_session, person=person)

    assert schedule.id is not None
    assert len(schedule.entries) == 5
    assert all(entry.hours == Decimal("8") for entry in schedule.entries)


def test_schedule_supports_uneven_days(db_session: Session) -> None:
    """Monday-Friday but Wednesday off, per CLAUDE.md's example schedules."""
    person = make_person(db_session)
    entries = [
        WorkingScheduleEntry(weekday=0, hours=Decimal("6")),
        WorkingScheduleEntry(weekday=1, hours=Decimal("6")),
        WorkingScheduleEntry(weekday=2, hours=Decimal("0")),
        WorkingScheduleEntry(weekday=3, hours=Decimal("6")),
        WorkingScheduleEntry(weekday=4, hours=Decimal("6")),
    ]
    schedule = make_working_schedule(db_session, person=person, entries=entries)

    wednesday = next(e for e in schedule.entries if e.weekday == 2)
    assert wednesday.hours == Decimal("0")


def test_duplicate_weekday_in_same_schedule_is_rejected(db_session: Session) -> None:
    person = make_person(db_session)
    entries = [
        WorkingScheduleEntry(weekday=0, hours=Decimal("8")),
        WorkingScheduleEntry(weekday=0, hours=Decimal("4")),
    ]
    with pytest.raises(IntegrityError):
        make_working_schedule(db_session, person=person, entries=entries)


def test_weekday_out_of_range_is_rejected(db_session: Session) -> None:
    person = make_person(db_session)
    entries = [WorkingScheduleEntry(weekday=7, hours=Decimal("8"))]
    with pytest.raises(IntegrityError):
        make_working_schedule(db_session, person=person, entries=entries)


def test_hours_above_24_is_rejected(db_session: Session) -> None:
    person = make_person(db_session)
    entries = [WorkingScheduleEntry(weekday=0, hours=Decimal("25"))]
    with pytest.raises(IntegrityError):
        make_working_schedule(db_session, person=person, entries=entries)


def test_deleting_schedule_cascades_to_entries(db_session: Session) -> None:
    person = make_person(db_session)
    schedule = make_working_schedule(db_session, person=person)
    schedule_id = schedule.id

    db_session.delete(schedule)
    db_session.flush()

    remaining = db_session.scalar(
        select(func.count())
        .select_from(WorkingScheduleEntry)
        .where(WorkingScheduleEntry.working_schedule_id == schedule_id)
    )
    assert remaining == 0

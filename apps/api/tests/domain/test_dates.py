from datetime import date

import pytest

from app.domain.dates import iterate_dates, week_range


def test_iterate_dates_single_day() -> None:
    assert list(iterate_dates(date(2026, 8, 17), date(2026, 8, 17))) == [date(2026, 8, 17)]


def test_iterate_dates_full_week() -> None:
    days = list(iterate_dates(date(2026, 8, 17), date(2026, 8, 23)))
    assert len(days) == 7
    assert days[0] == date(2026, 8, 17)
    assert days[-1] == date(2026, 8, 23)


def test_iterate_dates_crosses_month_boundary() -> None:
    days = list(iterate_dates(date(2026, 1, 30), date(2026, 2, 2)))
    assert days == [date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 2)]


def test_iterate_dates_crosses_year_boundary() -> None:
    days = list(iterate_dates(date(2026, 12, 30), date(2027, 1, 2)))
    assert days == [
        date(2026, 12, 30),
        date(2026, 12, 31),
        date(2027, 1, 1),
        date(2027, 1, 2),
    ]


def test_iterate_dates_includes_leap_day() -> None:
    # 2028 is a leap year (divisible by 4, not a century).
    days = list(iterate_dates(date(2028, 2, 27), date(2028, 3, 1)))
    assert date(2028, 2, 29) in days
    assert len(days) == 4


def test_iterate_dates_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="end_date cannot precede start_date"):
        list(iterate_dates(date(2026, 8, 20), date(2026, 8, 17)))


def test_iterate_dates_is_idempotent() -> None:
    args = (date(2026, 8, 1), date(2026, 8, 10))
    assert list(iterate_dates(*args)) == list(iterate_dates(*args))


def test_week_range_for_monday_is_same_week() -> None:
    # 2026-08-17 is a Monday.
    assert week_range(date(2026, 8, 17)) == (date(2026, 8, 17), date(2026, 8, 23))


def test_week_range_for_sunday_is_the_week_ending_that_day() -> None:
    # 2026-08-23 is the Sunday of the same week as 2026-08-17.
    assert week_range(date(2026, 8, 23)) == (date(2026, 8, 17), date(2026, 8, 23))


def test_week_range_for_midweek_date() -> None:
    # 2026-08-19 is a Wednesday.
    assert week_range(date(2026, 8, 19)) == (date(2026, 8, 17), date(2026, 8, 23))

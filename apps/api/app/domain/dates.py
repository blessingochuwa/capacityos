"""Pure date-range helpers for the capacity engine.

No SQLAlchemy, no I/O — every capacity calculation works over explicit
[start_date, end_date] ranges (CLAUDE.md §4, spec §4), and this module is the
one place that defines the canonical week so the assumption isn't scattered
across the codebase.
"""

from collections.abc import Iterator
from datetime import date, timedelta

WEEK_START_WEEKDAY = 0
"""Canonical week starts Monday (date.weekday() convention: 0=Monday..6=Sunday),
matching WorkingScheduleEntry.weekday (see app/models/working_schedule.py)."""


def iterate_dates(start_date: date, end_date: date) -> Iterator[date]:
    """Every date in [start_date, end_date], inclusive, ascending.

    Raises ValueError if end_date < start_date rather than silently yielding
    nothing — an inverted range is a caller bug, not an empty period.
    """
    if end_date < start_date:
        raise ValueError("end_date cannot precede start_date")
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def week_range(any_date: date) -> tuple[date, date]:
    """The Monday..Sunday range containing any_date."""
    monday = any_date - timedelta(days=any_date.weekday() - WEEK_START_WEEKDAY)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def ranges_overlap(
    start_a: date | None, end_a: date | None, start_b: date | None, end_b: date | None
) -> bool:
    """Whether two nullable [start, end] ranges overlap. None on either end of
    a range means unbounded in that direction (see WorkingSchedule.effective_*).

    Promoted out of app/services/working_schedule.py (Phase 1) so Phase 6's
    import pre-check can simulate the same overlap rule in memory without a
    second implementation — see docs/adr/0006-phase-6-import-export.md.
    """
    a_starts_before_b_ends = start_a is None or end_b is None or start_a <= end_b
    b_starts_before_a_ends = start_b is None or end_a is None or start_b <= end_a
    return a_starts_before_b_ends and b_starts_before_a_ends

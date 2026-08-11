from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.person import Person


class WorkingSchedule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A person's normal recurring weekly working pattern — "when does this
    person normally work," NOT "when are they currently free" (that's
    AvailabilityException) and NOT "what work have they been assigned"
    (that's Allocation). See docs/domain-concepts.md for the full
    WORKING SCHEDULE / AVAILABILITY / ALLOCATION / CAPACITY distinction.

    effective_start_date/effective_end_date are both nullable: NULL start
    means "effective from the beginning of time," NULL end means
    "effective indefinitely." This lets a person have more than one
    WorkingSchedule over time (e.g. a part-time period) without a schema
    change; Phase 1 does not enforce non-overlap between a person's
    schedules — that validation belongs to a later phase once it's needed.

    The actual per-weekday hours live in WorkingScheduleEntry.
    """

    __tablename__ = "working_schedules"
    __table_args__ = (
        CheckConstraint(
            "effective_end_date IS NULL OR effective_start_date IS NULL "
            "OR effective_end_date >= effective_start_date",
            name="ck_working_schedule_effective_dates",
        ),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    effective_start_date: Mapped[date | None] = mapped_column(Date)
    effective_end_date: Mapped[date | None] = mapped_column(Date)

    person: Mapped[Person] = relationship(back_populates="working_schedules")
    entries: Mapped[list[WorkingScheduleEntry]] = relationship(
        back_populates="working_schedule",
        cascade="all, delete-orphan",
        order_by="WorkingScheduleEntry.weekday",
    )


class WorkingScheduleEntry(Base, UUIDPrimaryKeyMixin):
    """One weekday's normal working hours within a WorkingSchedule.

    weekday follows Python's date.weekday() convention: 0=Monday ... 6=Sunday
    (NOT the ISO 1-7 convention) — chosen because it's the standard-library
    default and is documented here explicitly to remove any ambiguity.

    hours has no floor above 0 (0 is valid — e.g. Wednesday off in a 4-day
    week) and a hard physical ceiling of 24 at the DB level; a stricter
    business-realistic ceiling can be added at the schema/service layer
    later without a migration.
    """

    __tablename__ = "working_schedule_entries"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_schedule_entry_weekday_range"),
        CheckConstraint("hours >= 0 AND hours <= 24", name="ck_schedule_entry_hours_range"),
        UniqueConstraint(
            "working_schedule_id", "weekday", name="uq_schedule_entry_schedule_weekday"
        ),
    )

    working_schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("working_schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)

    working_schedule: Mapped[WorkingSchedule] = relationship(back_populates="entries")

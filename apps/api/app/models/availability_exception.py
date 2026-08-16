from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AvailabilityType

if TYPE_CHECKING:
    from app.models.person import Person


class AvailabilityException(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A deviation from a person's normal WorkingSchedule over
    [start_date, end_date] — e.g. leave, a public holiday, training.

    SEMANTICS (read this before touching hours):
    hours = NULL means the person is completely unavailable for the whole
    period (the common case: annual leave, sick leave, public holiday).
    hours = a numeric value means the person is available for that many
    hours PER DAY during the period (partial availability — e.g. a person
    who normally works 8 hours/day is available for only 4 hours/day for
    this period). hours is never "hours missed."

    availability_type is a controlled vocabulary (AvailabilityType) but,
    unlike the other enum columns in this schema, has NO DB CHECK
    constraint (native_enum=False, create_constraint=False below) — the
    spec is explicit that availability reasons must not be hard-coded into
    the database structure, so extending the list is a pure code change.

    This model does not calculate remaining capacity — see Allocation and
    docs/domain-concepts.md.
    """

    __tablename__ = "availability_exceptions"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_availability_end_after_start"),
        CheckConstraint("hours IS NULL OR hours >= 0", name="ck_availability_hours_nonnegative"),
        Index("ix_availability_person_dates", "person_id", "start_date", "end_date"),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    availability_type: Mapped[AvailabilityType] = mapped_column(
        Enum(
            AvailabilityType,
            name="availability_type_enum",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=False,
        ),
        nullable=False,
    )
    hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)
    """Phase 6 import identity key — AvailabilityException has no other
    natural key. Nullable: most exceptions are created directly and never
    imported. See docs/adr/0006-phase-6-import-export.md."""

    person: Mapped[Person] = relationship(back_populates="availability_exceptions")

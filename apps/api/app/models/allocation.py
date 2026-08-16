from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AllocationUnit

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.project import Project


class Allocation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Planned allocation of a person's working capacity to a project:
    Person -> Project -> [start_date, end_date] -> allocation_hours.

    SEMANTICS (read this before touching allocation_hours):
    allocation_hours is the TOTAL planned hours for the whole
    [start_date, end_date] period — NOT a daily or weekly rate. An
    allocation of 40 hours over a 4-week period means 40 hours total across
    those 4 weeks, not 40 hours/day and not 40 hours/week. allocation_unit
    currently only has one member (AllocationUnit.TOTAL_HOURS) so this
    column can carry a different unit (e.g. hours per week) in a future
    phase without a schema rewrite — see docs/domain-concepts.md.

    This model does not calculate utilization, remaining capacity, or
    over-allocation — those are derived by a future capacity engine reading
    Allocation + WorkingSchedule + AvailabilityException together.
    """

    __tablename__ = "allocations"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_allocation_end_after_start"),
        CheckConstraint("allocation_hours >= 0", name="ck_allocation_hours_nonnegative"),
        Index("ix_allocation_person_dates", "person_id", "start_date", "end_date"),
        Index("ix_allocation_project_dates", "project_id", "start_date", "end_date"),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    allocation_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    allocation_unit: Mapped[AllocationUnit] = mapped_column(
        Enum(
            AllocationUnit,
            name="ck_allocations_allocation_unit",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=AllocationUnit.TOTAL_HOURS,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)
    """Phase 6 import identity key — Allocation has no other natural key.
    Nullable: most allocations are created directly and never imported. See
    docs/adr/0006-phase-6-import-export.md."""

    person: Mapped[Person] = relationship(back_populates="allocations")
    project: Mapped[Project] = relationship(back_populates="allocations")

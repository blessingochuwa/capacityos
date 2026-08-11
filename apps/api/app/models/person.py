from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import EmploymentStatus

if TYPE_CHECKING:
    from app.models.allocation import Allocation
    from app.models.availability_exception import AvailabilityException
    from app.models.team_membership import TeamMembership
    from app.models.working_schedule import WorkingSchedule


class Person(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An individual resource in the organization.

    Person deliberately holds no project-allocation, working-schedule, or
    availability data directly — those are separate entities (see
    docs/domain-concepts.md) so this table only answers "who is this
    person," not "what is their capacity."

    display_name is stored (not a computed property) so it's queryable/
    sortable in SQL, but there is exactly one place that decides its value
    when not explicitly supplied: PersonService.create, which defaults it
    to "{first_name} {last_name}". Callers may still override it (e.g. a
    preferred name), so it is not a strict function of first/last name.

    A person may belong to zero, one, or many teams — see TeamMembership.
    """

    __tablename__ = "people"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    job_title: Mapped[str | None] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        Enum(
            EmploymentStatus,
            name="ck_people_employment_status",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=EmploymentStatus.ACTIVE,
    )

    team_memberships: Mapped[list[TeamMembership]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    allocations: Mapped[list[Allocation]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    working_schedules: Mapped[list[WorkingSchedule]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    availability_exceptions: Mapped[list[AvailabilityException]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )

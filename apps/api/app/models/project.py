from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ProjectStatus

if TYPE_CHECKING:
    from app.models.allocation import Allocation
    from app.models.project_skill_requirement import ProjectSkillRequirement
    from app.models.risk import Risk
    from app.models.stakeholder import Stakeholder


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A project/workstream that consumes one organization's capacity
    (Phase 12).

    start_date/end_date are nullable — a project can exist in "planned"
    status before its dates are known. When both are set, end must not
    precede start (enforced by DB CHECK and mirrored in ProjectCreate/
    ProjectUpdate for a clean 422 instead of an IntegrityError).

    Person-specific allocation data does not live here — see Allocation.

    external_id was globally unique through Phase 11; Phase 12 rescopes it
    to (organization_id, external_id) — NULLs don't collide under this
    constraint in either SQLite or PostgreSQL, so no partial/filtered
    index is needed for the common "never imported" case.
    """

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_project_end_after_start",
        ),
        UniqueConstraint(
            "organization_id", "external_id", name="uq_project_organization_external_id"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            name="ck_projects_status",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=ProjectStatus.PLANNED,
        index=True,
    )
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    """Phase 6 import identity key — Project has no other natural key (name
    is not unique). Nullable: most projects are created directly through the
    UI/API and never imported. See docs/adr/0006-phase-6-import-export.md."""

    allocations: Mapped[list[Allocation]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    skill_requirements: Mapped[list[ProjectSkillRequirement]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    risks: Mapped[list[Risk]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    stakeholders: Mapped[list[Stakeholder]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

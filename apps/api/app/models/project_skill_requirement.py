from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SkillProficiency

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.skill import Skill


class ProjectSkillRequirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A capability a project needs, and how much of it (Phase 7).

    required_hours mirrors Allocation.allocation_hours semantics: a TOTAL
    over the queried period, not a daily/weekly rate (see
    docs/domain-concepts.md). minimum_proficiency is nullable — null means
    any recorded proficiency in this skill qualifies (see
    app/domain/skills.py::is_qualified). (project_id, skill_id) is unique:
    a project has at most one active requirement row per skill — adjusting
    required hours means updating this row, not adding a second one.
    """

    __tablename__ = "project_skill_requirements"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "skill_id", name="uq_project_skill_requirement_project_skill"
        ),
        CheckConstraint("required_hours > 0", name="ck_project_skill_requirement_hours_positive"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    required_hours: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    minimum_proficiency: Mapped[SkillProficiency | None] = mapped_column(
        Enum(
            SkillProficiency,
            name="ck_project_skill_requirements_min_proficiency",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
    )
    notes: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="skill_requirements")
    skill: Mapped[Skill] = relationship(back_populates="project_requirements")

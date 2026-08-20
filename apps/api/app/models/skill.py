from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.person_skill import PersonSkill
    from app.models.project_skill_requirement import ProjectSkillRequirement


class Skill(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A named capability people can hold and projects can require, scoped
    to one organization (Phase 7, Phase 12).

    is_active is a soft-delete flag, not a hard DELETE — PersonSkill and
    ProjectSkillRequirement rows reference a skill by id, and deactivating
    (rather than removing) preserves those historical records instead of
    cascading into an orphan/invalid state or silently changing past
    coverage calculations. Qualification and coverage calculations
    deliberately ignore inactive skills even where a stale PersonSkill/
    ProjectSkillRequirement row still references one (CLAUDE.md invariant:
    "inactive skills should not accidentally appear as active requirements")
    — see docs/adr/0007-phase-7-skills-bottleneck-analysis.md.

    name was globally unique through Phase 11; Phase 12 rescopes it to
    (organization_id, name) — two unrelated organizations may both
    plausibly have a skill named "Python" or "Figma".
    """

    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_skill_organization_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    person_skills: Mapped[list[PersonSkill]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )
    project_requirements: Mapped[list[ProjectSkillRequirement]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )

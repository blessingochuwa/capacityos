from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MoscowCategory

if TYPE_CHECKING:
    from app.models.prioritization_framework import PrioritizationFramework
    from app.models.project import Project
    from app.models.project_priority_criterion_value import ProjectPriorityCriterionValue


class ProjectPriorityScore(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One Project's recorded inputs against one PrioritizationFramework
    (Phase 17) — at most one per (project, framework) pair; scoring a
    project again under the same framework updates this row rather than
    creating a second one, so "rank portfolio" never has to decide which
    of several scores for the same pair is current.

    Deliberately holds no `score`/`rank` column — see
    app/domain/prioritization.py's module docstring: the computed score is
    always derived at read time from this row's criterion values (see
    ProjectPriorityCriterionValue) plus the framework's current criteria/
    weights, exactly like Risk.exposure is derived from probability x
    impact rather than stored. This also means a framework's weights can
    be edited and every existing score's ranking updates automatically
    the next time it's read, with no batch recomputation step required.

    CASCADE on project_id: a score is meaningless once its project is
    gone (matches Risk/Stakeholder's identical CASCADE). CASCADE on
    framework_id: matches the same reasoning, though in practice a
    framework is soft-deleted (is_active=False), not hard-deleted — see
    PrioritizationFramework's docstring.

    category (Phase 18) is the ONLY input a MOSCOW-framework score has —
    nullable because it's meaningless for every other framework_type
    (RICE/ICE/WSJF/WEIGHTED score through `values`/ProjectPriorityCriterionValue
    instead; a MOSCOW score has zero PrioritizationCriterion rows to
    attach a value to at all). Which column is actually used is decided
    entirely by the linked framework's framework_type, enforced at the
    service layer (app/services/project_priority_score.py), not by a DB
    CHECK spanning two tables.
    """

    __tablename__ = "project_priority_scores"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "framework_id", name="uq_project_priority_score_project_framework"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    framework_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prioritization_frameworks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    category: Mapped[MoscowCategory | None] = mapped_column(
        Enum(
            MoscowCategory,
            name="ck_project_priority_scores_category",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        )
    )

    project: Mapped[Project] = relationship(back_populates="priority_scores")
    framework: Mapped[PrioritizationFramework] = relationship()
    values: Mapped[list[ProjectPriorityCriterionValue]] = relationship(
        back_populates="score", cascade="all, delete-orphan"
    )

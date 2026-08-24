from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

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

    project: Mapped[Project] = relationship(back_populates="priority_scores")
    framework: Mapped[PrioritizationFramework] = relationship()
    values: Mapped[list[ProjectPriorityCriterionValue]] = relationship(
        back_populates="score", cascade="all, delete-orphan"
    )

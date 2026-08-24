from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.prioritization_criterion import PrioritizationCriterion
    from app.models.project_priority_score import ProjectPriorityScore


class ProjectPriorityCriterionValue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One submitted value for one criterion, within one
    ProjectPriorityScore (Phase 17). The only fact this phase actually
    persists for scoring purposes — the criterion's human judgment input
    (e.g. "Reach = 8000") that cannot be deterministically re-derived from
    anything else in the system, unlike the score itself.

    No organization_id here — a leaf-of-leaf row always reached only
    through its already-scoped parent (ProjectPriorityScore), never
    queried independently. Matches WorkingScheduleEntry/ScenarioOperation's
    exact precedent (see docs/adr/0012-organizations-multi-tenancy.md).

    CASCADE on both FKs: a value is meaningless without its score, and a
    value for a criterion that was removed from its (Weighted Scoring)
    framework is meaningless too — see PrioritizationCriterion's docstring
    on why criterion deletion is a real hard delete, not a soft one.
    """

    __tablename__ = "project_priority_criterion_values"
    __table_args__ = (
        UniqueConstraint(
            "score_id", "criterion_id", name="uq_priority_criterion_value_score_criterion"
        ),
    )

    score_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_priority_scores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criterion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prioritization_criteria.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    score: Mapped[ProjectPriorityScore] = relationship(back_populates="values")
    criterion: Mapped[PrioritizationCriterion] = relationship()

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.prioritization_framework import PrioritizationFramework


class PrioritizationCriterion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One scoring input belonging to exactly one PrioritizationFramework
    (Phase 17).

    `key` is the stable, machine-readable identifier
    app/domain/prioritization.py's formulas key off of (e.g. "reach" for
    RICE) — `name` is the human-readable label shown in the UI, which
    (for a Weighted Scoring framework) an organization may set freely.

    `is_editable` distinguishes the two v1 framework types' criteria
    (see docs/PRD-phase-17-prioritization.md §5 / Open Question 3): RICE's
    four criteria are fixed by the framework definition itself and seeded
    with is_editable=False when the framework is created — an organization
    cannot rename, reweight, or remove them (attempting to is a
    ForbiddenError, not a missing feature). Weighted Scoring's criteria are
    entirely organization-defined (is_editable=True) — name, weight, and
    existence are all under the organization's control.

    `weight` is meaningful only for Weighted Scoring — RICE's formula
    ((Reach x Impact x Confidence) / Effort) does not use a weight at all,
    so it stays NULL for RICE's seeded criteria rather than an unused
    default that would misleadingly suggest RICE is weight-driven.
    """

    __tablename__ = "prioritization_criteria"
    __table_args__ = (
        UniqueConstraint(
            "framework_id", "key", name="uq_prioritization_criterion_framework_key"
        ),
    )

    framework_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prioritization_frameworks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    is_editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    framework: Mapped[PrioritizationFramework] = relationship(back_populates="criteria")

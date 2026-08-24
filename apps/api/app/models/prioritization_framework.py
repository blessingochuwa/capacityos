from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PrioritizationFrameworkType

if TYPE_CHECKING:
    from app.models.prioritization_criterion import PrioritizationCriterion


class PrioritizationFramework(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An organization-chosen method for ranking Projects (Phase 17,
    CLAUDE.md §18) — "Do not prescribe one prioritization framework as
    universally correct." An organization may define several (e.g. RICE
    for feature work, a custom weighted framework for platform work);
    `framework_type` selects which pure function in
    app/domain/prioritization.py combines its criteria into a score — see
    docs/PRD-phase-17-prioritization.md §5 for why RICE/ICE/WSJF and
    Weighted Scoring all share this one storage shape rather than each
    getting a bespoke table.

    is_active is a soft-delete flag, matching Skill's exact precedent —
    ProjectPriorityScore rows reference a framework by id, and
    deactivating (rather than removing) preserves those historical scores
    instead of orphaning them. A deactivated framework is excluded from
    portfolio ranking but its already-recorded scores remain readable.

    framework_type is NOT DB-CHECK-constrained — see
    PrioritizationFrameworkType's own docstring for why.
    """

    __tablename__ = "prioritization_frameworks"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", name="uq_prioritization_framework_organization_name"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    framework_type: Mapped[PrioritizationFrameworkType] = mapped_column(
        Enum(
            PrioritizationFrameworkType,
            name="ck_prioritization_frameworks_framework_type",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=False,
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    criteria: Mapped[list[PrioritizationCriterion]] = relationship(
        back_populates="framework",
        cascade="all, delete-orphan",
        order_by="PrioritizationCriterion.sequence",
    )

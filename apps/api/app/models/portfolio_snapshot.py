from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PrioritizationFrameworkType

if TYPE_CHECKING:
    from app.models.prioritization_framework import PrioritizationFramework


class PortfolioSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An explicit, user-triggered, immutable record of one framework's
    computed portfolio ranking at a point in time (Phase 21 — see
    docs/adr/0021-portfolio-snapshots.md and
    docs/PRD-phase-17-prioritization.md's original §8 proposal).

    Deliberately NOT read back as an input to any live computation — the
    live portfolio board (ProjectPriorityScoreService.rank_portfolio)
    always computes fresh, exactly as it did before this table existed.
    A snapshot is created only by an explicit action ("save this
    ranking"), for trend/history purposes.

    `created_at` (TimestampMixin) IS the "taken at" moment — no separate
    column, matching AuditEvent's own precedent where created_at already
    means "when this happened" for an immutable historical record.

    `framework_name`/`framework_type` are frozen copies of the linked
    framework's values AT THE MOMENT OF CAPTURE, not a live join — a
    framework's name is editable (PrioritizationFrameworkUpdate.name), and
    a snapshot's entire purpose is historical reproducibility: if an
    organization renames "Q3 RICE" to "Q3 RICE (retired)" next quarter,
    a snapshot taken under the old name must still show the old name.
    `framework_type` never actually changes post-creation, but is frozen
    here too so a snapshot is a fully self-contained record that never
    needs to join back to prioritization_frameworks to render.

    `entries` is a JSON array, one object per project that was ranked at
    capture time: {project_id, project_name, score (Decimal-as-string or
    null), rank (int or null), missing_criteria, breakdown (criterion key
    -> Decimal-as-string), category}. Every value is frozen at capture
    time for the same reproducibility reason as framework_name above — a
    project rename, a later re-score, or a project's deletion must never
    change what an already-taken snapshot shows. See
    app/services/portfolio_snapshot.py for how this is built from
    ProjectPriorityScoreService.rank_portfolio's live result.

    FK on framework_id is RESTRICT, matching organization_id's own
    convention — frameworks are soft-deleted only
    (PrioritizationFrameworkService.deactivate sets is_active=False, see
    prioritization_framework.py), never hard-deleted, so this is a safety
    net for a deletion path that does not currently exist rather than a
    behavior that will ever actually trigger.

    No PATCH/DELETE route exists for this entity — immutable and
    append-only, matching AuditEvent's own shape exactly.
    """

    __tablename__ = "portfolio_snapshots"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    framework_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prioritization_frameworks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    framework_name: Mapped[str] = mapped_column(nullable=False)
    framework_type: Mapped[PrioritizationFrameworkType] = mapped_column(
        Enum(
            PrioritizationFrameworkType,
            name="ck_portfolio_snapshots_framework_type",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
    )
    entries: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    """See the class docstring — untyped JSON like AuditEvent.event_metadata,
    reconstructed into PortfolioSnapshotEntryRead's strict types
    (Decimal/UUID/enum) only at the schema boundary
    (app/schemas/prioritization.py::portfolio_snapshot_to_read)."""

    framework: Mapped[PrioritizationFramework] = relationship()

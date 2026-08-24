from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MoscowCategory

if TYPE_CHECKING:
    from app.models.prioritization_framework import PrioritizationFramework
    from app.models.project import Project
    from app.models.scenario import Scenario


class ScenarioPriorityOverride(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One Scenario's hypothetical prioritization inputs for one Project
    under one PrioritizationFramework (Phase 20 — see
    docs/adr/0020-scenario-priority-comparison.md).

    Deliberately NOT a ScenarioOperation: the 8 ScenarioOperationType
    values (app/models/enums.py) are all capacity/allocation concerns,
    replayed in sequence through PlanningState
    (app/domain/scenario.py) — a prioritization override has no ordering
    semantics (it's a value, not a delta-in-a-sequence) and never touches
    capacity, so it lives in its own table rather than extending that
    engine or its CHECK-constrained operation_type vocabulary.

    Never mutates ProjectPriorityScore/ProjectPriorityCriterionValue —
    this row is read ALONGSIDE the real baseline score
    (app/services/scenario_priority.py merges `values`/`category` on top
    of ProjectPriorityScoreService.values_dict's baseline dict, in
    memory, at read time) and is never written back to it. Deleting the
    Scenario or the Project cascades the override away with it; deleting
    the framework does too, since an override with no framework to score
    against is meaningless.

    At most one row per (scenario, project, framework) — matching
    ProjectPriorityScore's own one-row-per-(project,framework)
    uniqueness shape exactly, just scenario-scoped instead of
    persisted-baseline-scoped. Creating a second override for the same
    triple replaces the first (an upsert) rather than requiring a
    separate PATCH endpoint — see the ADR for why.

    `values` is a JSON dict of criterion_key -> Decimal-as-string
    (mirroring ScenarioOperation.payload's own Decimal-as-JSON-string
    convention, app/schemas/scenario.py::operation_payload_to_dict) — an
    upsert-per-key overlay on the baseline's own values, exactly like
    ProjectPriorityScoreUpdate.values already works for a real score.
    `category` (MoSCoW only) replaces the baseline's category outright
    when set, matching ProjectPriorityScoreUpdate.category's own
    replace-not-merge semantics — there's no partial-update concept for
    one categorical value.
    """

    __tablename__ = "scenario_priority_overrides"
    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "project_id",
            "framework_id",
            name="uq_scenario_priority_override_scenario_project_framework",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    framework_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prioritization_frameworks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    values: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    category: Mapped[MoscowCategory | None] = mapped_column(
        Enum(
            MoscowCategory,
            name="ck_scenario_priority_overrides_category",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        )
    )

    scenario: Mapped[Scenario] = relationship()
    project: Mapped[Project] = relationship()
    framework: Mapped[PrioritizationFramework] = relationship()

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ScenarioOperationType, ScenarioStatus


class Scenario(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A hypothetical planning exercise over [baseline_start_date,
    baseline_end_date] — see docs/domain-concepts.md ("Scenario Planning")
    and docs/adr/0004-phase-4-scenario-planning.md.

    Holds no calculation results and no copy of People/Projects/Allocations
    — a Scenario is its ScenarioOperations (the delta) plus this metadata.
    Calculating it always re-reads real baseline data at read time (see the
    ADR's "no caching" decision), so results are never stale relative to
    production data, only ever a function of (baseline data now, these
    operations).

    created_by is free text, not a foreign key to a user table — it predates
    Phase 10 authentication and is nullable rather than fabricated, per the
    original prompt's instruction not to invent user identities.

    organization_id (Phase 12) is the tenant boundary — a scenario's
    operations may only ever reference people/projects/allocations resolved
    through this same organization (enforced in app/services/scenario.py's
    _check_* methods), so the scenario itself can never straddle two
    organizations even though ScenarioOperation carries no FK of its own.
    """

    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint(
            "baseline_end_date >= baseline_start_date", name="ck_scenario_end_after_start"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ScenarioStatus] = mapped_column(
        Enum(
            ScenarioStatus,
            name="ck_scenarios_status",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=ScenarioStatus.DRAFT,
        index=True,
    )
    baseline_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    baseline_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(200))

    operations: Mapped[list[ScenarioOperation]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioOperation.sequence",
    )


class ScenarioOperation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One typed, hypothetical change within a Scenario.

    payload is JSON, but never reaches the service/domain layer unvalidated:
    app/schemas/scenario.py defines a Pydantic discriminated union keyed by
    operation_type, so the only way a payload is written is after passing
    the exact typed schema for its operation_type (see the ADR). No FK to
    Person/Project/Allocation from inside payload — those ids are validated
    at the service layer (existence-checked against real repositories, or
    against an earlier add_hypothetical_resource op in the same scenario)
    rather than by the database, because a payload may legitimately
    reference a hypothetical id that was never a real row.

    sequence is the deterministic application order (unique per scenario) —
    operations are never applied in creation-timestamp order, since a PATCH
    doesn't change when an operation conceptually "happens" in the scenario.
    """

    __tablename__ = "scenario_operations"
    __table_args__ = (
        UniqueConstraint("scenario_id", "sequence", name="uq_scenario_operation_sequence"),
    )

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation_type: Mapped[ScenarioOperationType] = mapped_column(
        Enum(
            ScenarioOperationType,
            name="ck_scenario_operations_operation_type",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    scenario: Mapped[Scenario] = relationship(back_populates="operations")

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RiskImpact, RiskProbability, RiskStatus

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.project import Project


class Risk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A project risk (Phase 13, CLAUDE.md §17) — description, cause,
    potential effect, probability, impact, response, owner, status, and a
    review date, scoped to exactly one Project (organization-scoped per
    Phase 12).

    exposure is deliberately NOT a column here — CLAUDE.md §17: "Do not
    create risk scores that imply false precision." It is always derived
    at read time from probability x impact via the explicit lookup table
    in app/domain/risk.py::calculate_risk_exposure, so it can never go
    stale relative to the two facts it depends on and is never a
    persisted number implying more precision than a coarse qualitative
    judgment actually has.

    owner_person_id is nullable and ON DELETE SET NULL — CLAUDE.md §5:
    "every important... risk... should have an accountable owner," but
    the risk record must outlive whichever Person currently owns it
    (matches User.person_id's own SET NULL precedent) rather than being
    deleted or blocked when that person leaves the roster. It points at
    Person, not User (CLAUDE.md §9: Person answers "who is being
    planned," User answers "who is logged in" — a risk owner is an
    accountable individual, not necessarily someone with system access).
    """

    __tablename__ = "risks"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cause: Mapped[str | None] = mapped_column(Text)
    potential_effect: Mapped[str | None] = mapped_column(Text)
    probability: Mapped[RiskProbability] = mapped_column(
        Enum(
            RiskProbability,
            name="ck_risks_probability",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=RiskProbability.MEDIUM,
    )
    impact: Mapped[RiskImpact] = mapped_column(
        Enum(
            RiskImpact,
            name="ck_risks_impact",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=RiskImpact.MEDIUM,
    )
    response: Mapped[str | None] = mapped_column(Text)
    owner_person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[RiskStatus] = mapped_column(
        Enum(
            RiskStatus,
            name="ck_risks_status",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=RiskStatus.OPEN,
        index=True,
    )
    review_date: Mapped[date | None] = mapped_column(Date)

    project: Mapped[Project] = relationship(back_populates="risks")
    owner: Mapped[Person | None] = relationship()

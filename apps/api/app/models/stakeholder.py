from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    StakeholderDecisionAuthority,
    StakeholderInfluence,
    StakeholderInterest,
)

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.project import Project


class Stakeholder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A project stakeholder (Phase 14, CLAUDE.md §16) — role, influence,
    interest, decision authority, and communication needs, scoped to
    exactly one Project (organization-scoped like every entity since
    Phase 12; "relevant project/work context" from §16's field list is
    satisfied by this scoping itself, not a separate stored field).

    name is always required and always stored explicitly — a stakeholder
    is not forced into the internal Person model. person_id is an
    OPTIONAL link to an existing Person for stakeholders who are also
    staffed people tracked for capacity; many real stakeholders (clients,
    regulators, an executive at a partner organization) are never a
    Person row at all, and requiring one would either fabricate a Person
    that doesn't belong on any capacity plan or block recording a real
    stakeholder. When person_id IS set, name is still the stakeholder's
    own recorded identity — never silently overwritten by the linked
    Person's display_name, so a rename of one never surprises the other.

    person_id is nullable and ON DELETE SET NULL — matches Risk.
    owner_person_id's precedent exactly: the stakeholder record outlives
    whichever Person it happens to be linked to.

    influence/interest/decision_authority are stored 3-tier enums (never
    a numeric score — CLAUDE.md §16/§17's "no false precision" applies
    here exactly as it does to Risk). communication_needs is free text
    (open vocabulary, like AvailabilityType — communication preferences
    vary too much across projects/organizations to fit a fixed set).
    """

    __tablename__ = "stakeholders"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "person_id", name="uq_stakeholder_project_person"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), index=True
    )
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    influence: Mapped[StakeholderInfluence] = mapped_column(
        Enum(
            StakeholderInfluence,
            name="ck_stakeholders_influence",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=StakeholderInfluence.MEDIUM,
    )
    interest: Mapped[StakeholderInterest] = mapped_column(
        Enum(
            StakeholderInterest,
            name="ck_stakeholders_interest",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=StakeholderInterest.MEDIUM,
    )
    decision_authority: Mapped[StakeholderDecisionAuthority] = mapped_column(
        Enum(
            StakeholderDecisionAuthority,
            name="ck_stakeholders_decision_authority",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=StakeholderDecisionAuthority.INFORMED,
    )
    communication_needs: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="stakeholders")
    person: Mapped[Person | None] = relationship()

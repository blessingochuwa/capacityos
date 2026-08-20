from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.team import Team


class TeamMembership(Base, UUIDPrimaryKeyMixin):
    """The Person <-> Team association.

    Deliberately a real table (not a plain many-to-many secondary table) so
    future metadata (role within team, primary-team flag, membership
    effective dates) can be added without a structural rewrite — see
    docs/adr/0002-phase-1-domain-foundation.md.

    Only created_at is tracked (no updated_at): membership rows are added or
    removed, not edited in place, for Phase 1.
    """

    __tablename__ = "team_memberships"
    __table_args__ = (
        UniqueConstraint("person_id", "team_id", name="uq_team_membership_person_team"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    person: Mapped[Person] = relationship(back_populates="team_memberships")
    team: Mapped[Team] = relationship(back_populates="memberships")

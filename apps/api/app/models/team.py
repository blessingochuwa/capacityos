from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.team_membership import TeamMembership


class Team(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A delivery team belonging to one organization (Phase 12). Membership
    is via TeamMembership, not a foreign key here — a team has many people
    and a person has many teams (see docs/domain-concepts.md).

    name was globally unique through Phase 11; Phase 12 rescopes it to
    (organization_id, name) — two unrelated organizations may both
    plausibly have a team called "Design" or "Platform".
    """

    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_team_organization_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    memberships: Mapped[list[TeamMembership]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )

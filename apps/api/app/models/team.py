from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.team_membership import TeamMembership


class Team(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An organizational or delivery team. Membership is via TeamMembership,
    not a foreign key here — a team has many people and a person has many
    teams (see docs/domain-concepts.md).
    """

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    memberships: Mapped[list[TeamMembership]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )

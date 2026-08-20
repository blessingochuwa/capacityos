from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, utcnow


class ProjectAccessGrant(Base, UUIDPrimaryKeyMixin):
    """An explicit Manager-level write/delete grant for one User on one
    Project (Phase 11). See TeamAccessGrant's docstring for the full
    rationale — this is the identical shape, keyed on project_id instead of
    team_id. Covers Project itself, ProjectSkillRequirement, and Allocation
    (via project_id) — see
    docs/adr/0011-instance-level-resource-authorization.md for exactly
    which routes consult it. organization_id (Phase 12) is defense-in-
    depth — see TeamAccessGrant's docstring for the full rationale.
    """

    __tablename__ = "project_access_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_project_access_grant_user_project"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

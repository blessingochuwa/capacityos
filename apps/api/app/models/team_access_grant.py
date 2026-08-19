from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, utcnow


class TeamAccessGrant(Base, UUIDPrimaryKeyMixin):
    """An explicit Manager-level write/delete grant for one User on one
    Team (Phase 11). Owner/Admin never consult this table — their bypass is
    role-based, enforced in app/domain/authorization.py::has_permission.
    Member/Viewer never consult it either — they hold no team.write/delete
    permission to begin with, so the type-level check in has_permission
    already denies them before a resource lookup would matter. Only Manager
    write/delete actions on Team/TeamMembership check it; Manager READ
    access to teams stays global (see
    docs/adr/0011-instance-level-resource-authorization.md).

    Only created_at is tracked (no updated_at) — a grant is added or
    removed, not edited in place, matching TeamMembership's precedent.
    Revocation is a hard delete: this is a pure access-control record, not
    a business entity with retained history value — the append-only
    AuditEvent trail (access_grant.create/access_grant.revoke) is what
    preserves who granted/revoked what and when, not this table.
    """

    __tablename__ = "team_access_grants"
    __table_args__ = (
        UniqueConstraint("user_id", "team_id", name="uq_team_access_grant_user_team"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

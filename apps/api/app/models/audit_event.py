from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, utcnow
from app.models.enums import AuditOutcome

# metadata is the natural column name here but collides with
# Base.metadata (SQLAlchemy's own declarative attribute) if used as the
# Python attribute name — mapped to the DB column "metadata" via
# mapped_column's positional name argument, exposed as event_metadata.


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """A durable, queryable record of a security-relevant or mutating action
    (Phase 10) — see docs/adr/0010-authentication-rbac-audit.md.

    Append-only by construction: no service method updates or deletes a row,
    and GET /api/v1/audit (Admin/Owner only) is the only route touching this
    table. actor_email is a denormalized snapshot (not just a join through
    actor_user_id) so a record stays readable even after the acting user is
    renamed or deactivated, and so a login-failure against an unknown email
    can still be recorded without actor_user_id.

    event_metadata is deliberately minimal per action type (e.g. an old/new
    role pair for a role change, entity type + row counts for an import) —
    never a raw request body, uploaded file content, AI prompt/context, or
    any secret. action uses AuditAction (app/models/enums.py), an open,
    non-DB-constrained vocabulary so a new audited action is a pure code
    change, never a migration.
    """

    __tablename__ = "audit_events"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[AuditOutcome] = mapped_column(
        Enum(
            AuditOutcome,
            name="ck_audit_events_outcome",
            native_enum=False,
            validate_strings=True,
            length=16,
            create_constraint=True,
        ),
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(String(64))
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)

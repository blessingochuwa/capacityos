import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class UUIDPrimaryKeyMixin:
    """UUID primary key, generated application-side so it's known before flush."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """created_at/updated_at as timezone-aware UTC timestamps.

    Set application-side (not server_default) so behavior is identical across
    SQLite (dev) and PostgreSQL (production) without relying on either
    database's clock/functions.
    """

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

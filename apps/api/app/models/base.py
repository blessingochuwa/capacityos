import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Normalizes a possibly-naive datetime read back from the database to
    UTC-aware. SQLite's DateTime(timezone=True) type (unlike PostgreSQL's)
    does not preserve tzinfo across a write/read round-trip — a value
    stored as UTC-aware comes back naive. Values already stored are always
    UTC (see utcnow() above), so a naive value is assumed to already be UTC,
    never re-interpreted in local time. Any code comparing a persisted
    datetime against utcnow() (e.g. app/services/auth.py's session/lockout
    expiry checks) must normalize through this first — comparing an aware
    and a naive datetime raises TypeError."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


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

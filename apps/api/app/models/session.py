from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, utcnow


class UserSession(Base, UUIDPrimaryKeyMixin):
    """A live login session (Phase 10).

    Named UserSession, not Session, to avoid colliding with
    sqlalchemy.orm.Session — every repository/service in this codebase
    already imports that name constantly.

    token_hash stores SHA-256(raw token), never the raw token itself — the
    raw token only ever exists in the httpOnly response cookie and in
    memory for the duration of one request; a read-only database compromise
    cannot be replayed into a valid session. expires_at is a fixed absolute
    TTL set at login (Settings.session_ttl_hours) — deliberately no silent
    sliding renewal, so a stolen-but-unused session token still expires.
    last_seen_at is updated at most once every 5 minutes per session (see
    AuthService) to avoid a database write on every authenticated request.
    Logout deletes the row outright; AuditEvent is the durable record that a
    logout happened, this table is only the live-session cache.

    csrf_token_hash is a SEPARATE random value from token_hash, not derived
    from it — the CSRF cookie carrying its raw form is deliberately NOT
    httpOnly (the frontend must be able to read it and echo it back as the
    X-CSRF-Token header), so it must never be the same secret as the
    session token itself; reusing that value would let anything able to
    read the CSRF cookie (e.g. an XSS payload) impersonate the session,
    defeating the whole point of the session cookie being httpOnly.
    """

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

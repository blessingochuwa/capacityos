import uuid
from datetime import datetime
from typing import Any

from app.models.audit_event import AuditEvent
from app.models.enums import AuditOutcome
from app.repositories.audit_event import AuditEventRepository


class AuditService:
    """Records and lists persistent AuditEvent rows (Phase 10). Append-only
    by construction — no update/delete method exists here or anywhere else
    in the codebase. See docs/adr/0010-authentication-rbac-audit.md.

    Called explicitly, once, from the route layer after a mutating call
    succeeds (or from a permission-check dependency on denial) — never from
    inside an existing Phase 1-9 service, so none of those gain an actor
    parameter or an audit-awareness dependency.

    record() commits immediately — the one deliberate, narrow exception to
    this codebase's "services never call commit()/rollback(), only
    app/core/database.py::get_db does" convention. This went through two
    designs before landing here, both caught by real testing rather than
    reasoned about in the abstract (see docs/adr/0010-authentication-rbac-
    audit.md):

    1. First attempt: commit the request-scoped `db` session directly.
       Broke immediately — SQLAlchemy's default expire_on_commit=True
       expired every ORM object already mutated earlier in the same
       request, so a subsequent re-read silently reflected the database's
       stored representation (e.g. a Decimal re-read as "4.00" instead of
       the "4" the route just set). Caught by the backend test suite.

    2. Second attempt: give AuditService its own independent database
       session/connection, specifically to avoid touching `db`'s identity
       map. This avoided the expiry problem but introduced a worse one on
       real (file-backed) SQLite, which only allows ONE writer at a time:
       by the point almost every audit call happens, `db` already holds an
       open, uncommitted write of its own (the mutation the audit event is
       recording, or AuthService.login's failed_login_count increment) — a
       second connection's write blocks against that transaction until it
       times out with "database is locked", because that transaction can't
       release until THIS request finishes, which is waiting on the audit
       write to succeed. A structural deadlock, not mere contention. Only
       caught by manually running a real server against a real file — the
       test suite's in-memory SQLite (StaticPool, one shared connection)
       can't reproduce cross-connection lock contention at all.

    The fix here uses `db` (one writer, no deadlock) but toggles
    expire_on_commit off around just this commit, so the objects the route
    already mutated keep their in-memory values instead of being silently
    re-read from the database afterward."""

    def __init__(self, repository: AuditEventRepository) -> None:
        self.repository = repository

    def record(
        self,
        *,
        actor_user_id: uuid.UUID | None,
        actor_email: str | None,
        action: str,
        outcome: AuditOutcome,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request_id: str | None = None,
        organization_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            action=action,
            outcome=outcome,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            organization_id=organization_id,
            event_metadata=metadata,
        )
        self.repository.add(event)
        session = self.repository.session
        previous_expire_on_commit = session.expire_on_commit
        session.expire_on_commit = False
        try:
            session.commit()
        finally:
            session.expire_on_commit = previous_expire_on_commit
        return event

    def list(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditEvent], int]:
        """organization_id is required (Phase 12), not optional — an Admin
        in one organization must never be able to query another
        organization's audit trail (docs/adr/0012-organizations-multi-
        tenancy.md). Events with no organization_id at all (e.g. a login
        failure against an unknown email) are deliberately excluded from
        every organization-scoped query — they surface only through a
        platform-level view, which this phase does not add an API for."""
        return self.repository.list_filtered(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            start=start,
            end=end,
            limit=limit,
            offset=offset,
        )

"""Shared authentication/authorization FastAPI dependencies (Phase 10).

The one cross-cutting dependency module in this codebase — every other
`get_x_service` factory lives in its own router file (matching the existing
per-router convention), but get_current_user/require_permission/require_csrf
are used by every router, so they live here instead of being duplicated or
imported awkwardly from one arbitrary router module.
"""

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthenticatedError
from app.core.logging import request_id_var
from app.core.security import hash_token
from app.domain.authorization import Permission, has_permission
from app.models.enums import AuditAction, AuditOutcome
from app.models.user import User
from app.repositories.audit_event import AuditEventRepository
from app.repositories.session import UserSessionRepository
from app.repositories.user import UserRepository
from app.services.audit import AuditService
from app.services.auth import AuthService


def get_auth_service(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> AuthService:
    return AuthService(
        UserRepository(db),
        UserSessionRepository(db),
        session_ttl_hours=settings.session_ttl_hours,
    )


def get_audit_service(db: Session = Depends(get_db)) -> AuditService:
    """Deliberately the SAME request-scoped `db` session, not a second
    connection — see app/services/audit.py::AuditService.record for why a
    genuinely separate connection was tried and reverted. SQLite allows
    only one writer at a time; by the point most audit calls happen, `db`
    has already flushed an uncommitted write of its own (e.g. the new
    Person row, or AuthService.login's failed_login_count increment), so a
    second connection's write blocks against that open transaction until
    SQLite's busy_timeout gives up with "database is locked" — a real
    failure this codebase's live server (not just its in-memory-SQLite test
    suite) caught. Sharing `db` avoids a second writer entirely; record()'s
    own expire_on_commit toggle avoids the different problem that sharing
    the session used to cause."""
    return AuditService(AuditEventRepository(db))


def get_current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """401 if there's no session cookie, or it doesn't resolve to a live
    session for an active user. Also stashes the resolved session's
    csrf_token_hash on request.state so require_csrf (below) doesn't need a
    second database lookup — FastAPI caches this dependency's result per
    request, so declaring it again elsewhere in the same request's
    dependency graph doesn't re-run it."""
    token = request.cookies.get(settings.session_cookie_name)
    if token is None:
        raise UnauthenticatedError("Authentication required.")

    resolved = auth_service.resolve_session(token)
    if resolved is None:
        raise UnauthenticatedError("Session is invalid or has expired.")

    user, session = resolved
    request.state.csrf_token_hash = session.csrf_token_hash
    return user


def require_permission(permission: Permission) -> Callable[..., User]:
    """Dependency factory — `Depends(require_permission(Permission.X))`.
    403 (never 401 — get_current_user already ran) if the caller's role
    lacks the permission, recording a `permission.denied` AuditEvent first.
    Returns the current user so a route can declare only this dependency
    and still capture the actor, without a second Depends(get_current_user)
    (FastAPI would cache it identically either way, but this is the more
    readable single call site)."""

    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        audit_service: AuditService = Depends(get_audit_service),
    ) -> User:
        if not has_permission(current_user.role, permission):
            audit_service.record(
                actor_user_id=current_user.id,
                actor_email=current_user.email,
                action=AuditAction.PERMISSION_DENIED,
                outcome=AuditOutcome.DENIED,
                resource_type=permission.value.split(".")[0],
                request_id=request_id_var.get(),
                metadata={"permission": permission.value, "role": current_user.role.value},
            )
            raise ForbiddenError(
                f"You do not have permission to perform this action ({permission.value})."
            )
        return current_user

    return dependency


def require_csrf(
    request: Request,
    settings: Settings = Depends(get_settings),
    _current_user: User = Depends(get_current_user),
) -> None:
    """Double-submit CSRF defense-in-depth for mutating routes — the
    primary defense is SameSite=Lax + the CORS origin allowlist + JSON-only
    routes (see docs/adr/0010-authentication-rbac-audit.md). Depends on
    get_current_user first (declared as a parameter, not called directly)
    so request.state.csrf_token_hash is guaranteed to be set."""
    header_token = request.headers.get("X-CSRF-Token")
    csrf_token_hash: str | None = getattr(request.state, "csrf_token_hash", None)
    if not header_token or not csrf_token_hash:
        raise ForbiddenError("Missing CSRF token.")
    if hash_token(header_token) != csrf_token_hash:
        raise ForbiddenError("Invalid CSRF token.")

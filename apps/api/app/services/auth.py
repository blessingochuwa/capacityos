import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import generate_session_token, hash_password, hash_token, verify_password
from app.models.base import as_utc, utcnow
from app.models.enums import MembershipStatus, UserStatus
from app.models.organization_membership import OrganizationMembership
from app.models.session import UserSession
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.repositories.session import UserSessionRepository
from app.repositories.user import UserRepository

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)
SESSION_ACTIVITY_UPDATE_INTERVAL = timedelta(minutes=5)
"""last_seen_at is only written when it's this stale, to avoid a database
write on every single authenticated request."""


@dataclass(frozen=True)
class LoginResult:
    success: bool
    user: User | None
    token: str | None
    csrf_token: str | None
    reason: Literal["invalid_credentials", "locked"] | None
    active_organization_id: uuid.UUID | None = None


class AuthService:
    """Login/logout/session-resolution (Phase 10). See
    docs/adr/0010-authentication-rbac-audit.md for the enumeration-
    resistance and lockout design this implements.

    Deliberately does not call AuditService itself — every audit event this
    service's callers need (auth.login_success/failure/account_locked,
    auth.logout) is recorded by the route layer, which has the request
    context (request_id) this service doesn't need to know about."""

    def __init__(
        self,
        user_repository: UserRepository,
        session_repository: UserSessionRepository,
        membership_repository: OrganizationMembershipRepository,
        organization_repository: OrganizationRepository,
        *,
        session_ttl_hours: int,
    ) -> None:
        self.user_repository = user_repository
        self.session_repository = session_repository
        self.membership_repository = membership_repository
        self.organization_repository = organization_repository
        self.session_ttl_hours = session_ttl_hours

    def login(self, email: str, password: str) -> LoginResult:
        """Always performs a real Argon2 verify (verify_password's own dummy-
        hash fallback), and always returns the same reason for an unknown
        email vs a disabled account, so a caller can't distinguish "no such
        account" from "wrong password" — enumeration resistance (see the
        ADR's threat model). "locked" is reported distinctly only because
        the route layer needs it for the audit action, never in the
        response message the client sees."""
        user = self.user_repository.get_by_email(email)
        now = utcnow()

        if user is None:
            verify_password(password, None)
            return LoginResult(
                success=False, user=None, token=None, csrf_token=None, reason="invalid_credentials"
            )

        if user.locked_until is not None and as_utc(user.locked_until) > now:
            verify_password(password, None)
            return LoginResult(
                success=False, user=user, token=None, csrf_token=None, reason="locked"
            )

        if user.status != UserStatus.ACTIVE:
            verify_password(password, None)
            return LoginResult(
                success=False, user=user, token=None, csrf_token=None, reason="invalid_credentials"
            )

        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1
            locked_now = user.failed_login_count >= MAX_FAILED_LOGIN_ATTEMPTS
            if locked_now:
                user.locked_until = now + LOCKOUT_DURATION
            self.user_repository.session.flush()
            return LoginResult(
                success=False,
                user=user,
                token=None,
                csrf_token=None,
                reason="locked" if locked_now else "invalid_credentials",
            )

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        token = generate_session_token()
        csrf_token = generate_session_token()

        # Phase 12: auto-select the active organization only when it's
        # unambiguous. Zero memberships (a brand-new account not yet added
        # to any organization) or more than one both leave this NULL —
        # get_current_membership (app/api/deps.py) then requires an
        # explicit POST /auth/switch-organization before any
        # organization-scoped route will succeed; the frontend's
        # RequireAuth gate reacts to that state directly rather than this
        # service guessing which organization the caller meant.
        active_memberships = self.membership_repository.list_active_for_user(user.id)
        active_organization_id = (
            active_memberships[0].organization_id if len(active_memberships) == 1 else None
        )

        session = UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            csrf_token_hash=hash_token(csrf_token),
            active_organization_id=active_organization_id,
            expires_at=now + timedelta(hours=self.session_ttl_hours),
            last_seen_at=now,
        )
        self.session_repository.add(session)
        self.user_repository.session.flush()
        return LoginResult(
            success=True,
            user=user,
            token=token,
            csrf_token=csrf_token,
            reason=None,
            active_organization_id=active_organization_id,
        )

    def logout(self, token: str) -> None:
        self.session_repository.delete_by_token_hash(hash_token(token))

    def switch_organization(
        self, user: User, session: UserSession, organization_id: uuid.UUID
    ) -> OrganizationMembership:
        """Re-verifies an active membership for (user, organization_id) AND
        that the organization itself is active BEFORE updating the
        session's active_organization_id — the request body's
        organization_id is only ever a selector, never trusted as proof of
        membership on its own (Phase 12). Raises NotFoundError, not
        ForbiddenError, when no active membership exists for this pair —
        deliberately indistinguishable from "that organization doesn't
        exist," so a caller can't use this endpoint to enumerate
        organizations they don't belong to."""
        membership = self.membership_repository.get_by_user_and_org(user.id, organization_id)
        if membership is None or membership.status != MembershipStatus.ACTIVE:
            raise NotFoundError("Organization", organization_id)
        organization = self.organization_repository.get(organization_id)
        if organization is None or not organization.is_active:
            raise NotFoundError("Organization", organization_id)
        session.active_organization_id = organization_id
        self.session_repository.session.flush()
        return membership

    def resolve_session(self, token: str) -> tuple[User, UserSession] | None:
        """Returns the authenticated User plus its live UserSession row for
        a raw session token, or None if it's missing, expired, or belongs
        to a no-longer-active user. Never raises —
        app/api/deps.py::get_current_user turns None into the 401
        UnauthenticatedError. The session row is returned (not just the
        user) so the caller can read csrf_token_hash for require_csrf
        without a second database lookup.

        The returned session's active_organization_id is NOT re-validated
        against live membership/organization state here — that
        per-request re-verification is app/api/deps.py::get_current_
        membership's job (Phase 12), kept deliberately separate so this
        method stays a pure "is this token good" check, unchanged from
        Phase 10."""
        session = self.session_repository.get_by_token_hash(hash_token(token))
        if session is None:
            return None

        now = utcnow()
        if as_utc(session.expires_at) <= now:
            return None

        user = self.user_repository.get(session.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            return None

        if now - as_utc(session.last_seen_at) > SESSION_ACTIVITY_UPDATE_INTERVAL:
            session.last_seen_at = now
            self.session_repository.session.flush()

        return user, session

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise ForbiddenError("Current password is incorrect.")
        user.password_hash = hash_password(new_password)
        self.user_repository.session.flush()

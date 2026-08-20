import logging
import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_access_grant_service,
    get_audit_service,
    get_auth_service,
    get_current_user,
    require_csrf,
)
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import UnauthenticatedError
from app.core.logging import request_id_var
from app.models.enums import AuditAction, AuditOutcome
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeRead,
    SwitchOrganizationRequest,
    me_to_read,
)
from app.services.access_grant import AccessGrantService
from app.services.audit import AuditService
from app.services.auth import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
security_logger = logging.getLogger("capacityos.security")

CSRF_COOKIE_NAME = "capacityos_csrf"


def _set_session_cookies(
    response: Response, settings: Settings, token: str, csrf_token: str
) -> None:
    max_age = settings.session_ttl_hours * 3600
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


def _build_me(
    user: User,
    active_organization_id: uuid.UUID | None,
    *,
    db: Session,
    access_grants: AccessGrantService,
) -> MeRead:
    """Assembles MeRead for /auth/login, /auth/me, and
    /auth/switch-organization — one place that resolves the caller's
    memberships/organizations and, if an organization is active, their
    role/permissions/instance grants WITHIN it (Phase 12)."""
    membership_repository = OrganizationMembershipRepository(db)
    organization_repository = OrganizationRepository(db)

    memberships = membership_repository.list_active_for_user(user.id)
    organizations = organization_repository.list_by_ids(
        [m.organization_id for m in memberships]
    )

    active_membership: OrganizationMembership | None = None
    active_organization: Organization | None = None
    if active_organization_id is not None:
        active_membership = next(
            (m for m in memberships if m.organization_id == active_organization_id), None
        )
        active_organization = next(
            (o for o in organizations if o.id == active_organization_id), None
        )

    accessible_team_ids: list[uuid.UUID] = []
    accessible_project_ids: list[uuid.UUID] = []
    if active_membership is not None:
        accessible_team_ids = access_grants.accessible_team_ids(
            user.id, active_membership.organization_id
        )
        accessible_project_ids = access_grants.accessible_project_ids(
            user.id, active_membership.organization_id
        )

    return me_to_read(
        user,
        active_organization=active_organization,
        active_membership=active_membership,
        organizations=organizations,
        accessible_team_ids=accessible_team_ids,
        accessible_project_ids=accessible_project_ids,
    )


@router.post("/login", response_model=MeRead)
def login(
    data: LoginRequest,
    response: Response,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
    audit_service: AuditService = Depends(get_audit_service),
    access_grants: AccessGrantService = Depends(get_access_grant_service),
    db: Session = Depends(get_db),
) -> MeRead:
    result = auth_service.login(data.email, data.password)
    request_id = request_id_var.get()

    if not result.success:
        action = (
            AuditAction.AUTH_ACCOUNT_LOCKED
            if result.reason == "locked"
            else AuditAction.AUTH_LOGIN_FAILURE
        )
        audit_service.record(
            actor_user_id=result.user.id if result.user else None,
            actor_email=data.email,
            action=action,
            outcome=AuditOutcome.FAILURE,
            request_id=request_id,
        )
        security_logger.warning(
            "login failed",
            extra={"outcome": result.reason, "email_domain": data.email.split("@")[-1]},
        )
        # Same generic message regardless of reason — see the ADR's
        # enumeration-resistance rationale (unknown email, wrong password,
        # and a locked account are all indistinguishable to the caller).
        raise UnauthenticatedError("Invalid email or password.")

    assert result.user is not None and result.token is not None and result.csrf_token is not None
    _set_session_cookies(response, settings, result.token, result.csrf_token)
    audit_service.record(
        actor_user_id=result.user.id,
        actor_email=result.user.email,
        action=AuditAction.AUTH_LOGIN_SUCCESS,
        outcome=AuditOutcome.SUCCESS,
        request_id=request_id,
    )
    security_logger.info("login succeeded", extra={"user_id": str(result.user.id)})
    return _build_me(
        result.user, result.active_organization_id, db=db, access_grants=access_grants
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if token is not None:
        resolved = auth_service.resolve_session(token)
        auth_service.logout(token)
        if resolved is not None:
            user, _session = resolved
            audit_service.record(
                actor_user_id=user.id,
                actor_email=user.email,
                action=AuditAction.AUTH_LOGOUT,
                outcome=AuditOutcome.SUCCESS,
                request_id=request_id_var.get(),
            )
            security_logger.info("logout", extra={"user_id": str(user.id)})
    _clear_session_cookies(response, settings)


@router.get("/me", response_model=MeRead)
def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    access_grants: AccessGrantService = Depends(get_access_grant_service),
    db: Session = Depends(get_db),
) -> MeRead:
    active_organization_id = getattr(request.state, "active_organization_id", None)
    return _build_me(current_user, active_organization_id, db=db, access_grants=access_grants)


@router.post("/switch-organization", response_model=MeRead, dependencies=[Depends(require_csrf)])
def switch_organization(
    data: SwitchOrganizationRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    access_grants: AccessGrantService = Depends(get_access_grant_service),
    audit_service: AuditService = Depends(get_audit_service),
    db: Session = Depends(get_db),
) -> MeRead:
    """Re-verifies membership + organization active BEFORE updating the
    session (see AuthService.switch_organization) — the request body's
    organization_id is only ever a selector, never trusted as proof of
    membership. Needs the live UserSession row (not just the token), so it
    resolves it directly rather than depending on get_current_membership,
    which would incorrectly require an ALREADY-active organization just to
    switch into a different (or a first) one."""
    token = request.cookies.get(settings.session_cookie_name)
    resolved = auth_service.resolve_session(token) if token is not None else None
    if resolved is None:
        raise UnauthenticatedError("Session is invalid or has expired.")
    _user, session = resolved

    auth_service.switch_organization(current_user, session, data.organization_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.AUTH_ORGANIZATION_SWITCH,
        outcome=AuditOutcome.SUCCESS,
        request_id=request_id_var.get(),
        organization_id=data.organization_id,
    )
    return _build_me(current_user, data.organization_id, db=db, access_grants=access_grants)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    auth_service.change_password(current_user, data.current_password, data.new_password)

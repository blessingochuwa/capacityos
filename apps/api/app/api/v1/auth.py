import logging

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    get_access_grant_service,
    get_audit_service,
    get_auth_service,
    get_current_user,
    require_csrf,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthenticatedError
from app.core.logging import request_id_var
from app.models.enums import AuditAction, AuditOutcome
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest
from app.schemas.user import UserRead, user_to_read
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


@router.post("/login", response_model=UserRead)
def login(
    data: LoginRequest,
    response: Response,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
    audit_service: AuditService = Depends(get_audit_service),
    access_grants: AccessGrantService = Depends(get_access_grant_service),
) -> UserRead:
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
    return user_to_read(
        result.user,
        accessible_team_ids=access_grants.accessible_team_ids(result.user.id),
        accessible_project_ids=access_grants.accessible_project_ids(result.user.id),
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


@router.get("/me", response_model=UserRead)
def get_me(
    current_user: User = Depends(get_current_user),
    access_grants: AccessGrantService = Depends(get_access_grant_service),
) -> UserRead:
    return user_to_read(
        current_user,
        accessible_team_ids=access_grants.accessible_team_ids(current_user.id),
        accessible_project_ids=access_grants.accessible_project_ids(current_user.id),
    )


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

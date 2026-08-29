import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_audit_service, get_current_membership, require_csrf, require_permission
from app.core.database import get_db
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome, UserStatus
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.person import PersonRepository
from app.repositories.user import UserRepository
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserRead, UserUpdate, user_to_read
from app.services.audit import AuditService
from app.services.user import UserService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(UserRepository(db), PersonRepository(db))


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_user(
    data: UserCreate,
    current_user: User = Depends(require_permission(Permission.USER_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: UserService = Depends(get_user_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> UserRead:
    """Creates an account only — no role anywhere yet (Phase 12: see
    UserCreate's docstring). Give the new account a role in the acting
    organization separately via
    POST /organizations/{organization_id}/memberships."""
    user = service.create(membership.organization_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.USER_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="user",
        resource_id=str(user.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )
    return user_to_read(user)


@router.get("", response_model=Page[UserRead])
def list_users(
    q: str | None = Query(default=None, max_length=200),
    status_filter: UserStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.USER_READ)),
    service: UserService = Depends(get_user_service),
) -> Page[UserRead]:
    """Deliberately NOT organization-scoped (Decision 8) — an admin's
    "add an existing user to my organization" flow needs to find any
    account by email, not just accounts already in the acting
    organization. require_permission still requires an active
    organization context to reach this route at all; it just doesn't
    filter the account directory by it.

    Phase 34: `q` (case-insensitive substring over email/display_name) and
    `status` (exact match) are additional optional filters over that same
    unscoped directory — see UserRepository.list_filtered. Neither field is
    ever a credential; password_hash is never selectable through this
    route or serialized by UserRead."""
    items, total = service.list(q=q, status=status_filter, limit=limit, offset=offset)
    return Page[UserRead](items=[user_to_read(item) for item in items], total=total)


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.USER_READ)),
    service: UserService = Depends(get_user_service),
) -> UserRead:
    return user_to_read(service.get(user_id))


@router.patch("/{user_id}", response_model=UserRead, dependencies=[Depends(require_csrf)])
def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    current_user: User = Depends(require_permission(Permission.USER_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: UserService = Depends(get_user_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> UserRead:
    user = service.update(membership.organization_id, user_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=(
            AuditAction.USER_STATUS_CHANGE if data.status is not None else AuditAction.USER_UPDATE
        ),
        outcome=AuditOutcome.SUCCESS,
        resource_type="user",
        resource_id=str(user.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return user_to_read(user)

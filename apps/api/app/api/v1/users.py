import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_audit_service, require_csrf, require_permission
from app.core.database import get_db
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome
from app.models.user import User
from app.repositories.person import PersonRepository
from app.repositories.user import UserRepository
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserRead, UserRoleChange, UserUpdate, user_to_read
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
    service: UserService = Depends(get_user_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> UserRead:
    user = service.create(data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.USER_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="user",
        resource_id=str(user.id),
        request_id=request_id_var.get(),
        metadata={"role": user.role.value},
    )
    return user_to_read(user)


@router.get("", response_model=Page[UserRead])
def list_users(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.USER_READ)),
    service: UserService = Depends(get_user_service),
) -> Page[UserRead]:
    items, total = service.list(limit=limit, offset=offset)
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
    service: UserService = Depends(get_user_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> UserRead:
    user = service.update(user_id, data)
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
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return user_to_read(user)


@router.patch("/{user_id}/role", response_model=UserRead, dependencies=[Depends(require_csrf)])
def change_user_role(
    user_id: uuid.UUID,
    data: UserRoleChange,
    current_user: User = Depends(require_permission(Permission.USER_WRITE)),
    service: UserService = Depends(get_user_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> UserRead:
    old_role = service.get(user_id).role
    user = service.change_role(user_id, data.role, acting_user=current_user)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.USER_ROLE_CHANGE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="user",
        resource_id=str(user.id),
        request_id=request_id_var.get(),
        metadata={"role_from": old_role.value, "role_to": user.role.value},
    )
    return user_to_read(user)

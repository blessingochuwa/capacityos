import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_access_grant_service,
    get_audit_service,
    require_csrf,
    require_permission,
)
from app.core.database import get_db
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome
from app.models.user import User
from app.repositories.allocation import AllocationRepository
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.schemas.allocation import AllocationCreate, AllocationRead, AllocationUpdate
from app.schemas.common import Page
from app.services.access_grant import AccessGrantService
from app.services.allocation import AllocationService
from app.services.audit import AuditService

router = APIRouter(prefix="/api/v1/allocations", tags=["allocations"])


def get_allocation_service(db: Session = Depends(get_db)) -> AllocationService:
    return AllocationService(
        AllocationRepository(db), PersonRepository(db), ProjectRepository(db)
    )


@router.post(
    "", response_model=AllocationRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_allocation(
    data: AllocationCreate,
    current_user: User = Depends(require_permission(Permission.ALLOCATION_WRITE)),
    service: AllocationService = Depends(get_allocation_service),
    audit_service: AuditService = Depends(get_audit_service),
    access_grants: AccessGrantService = Depends(get_access_grant_service),
) -> AllocationRead:
    # project_id comes from the request body, not a path param, so this is
    # the inline invocation of the same enforce_project_access method
    # require_project_access uses for path-resolved routes (Phase 11) — see
    # docs/adr/0011-instance-level-resource-authorization.md.
    access_grants.enforce_project_access(
        current_user,
        data.project_id,
        Permission.ALLOCATION_WRITE,
        audit_service=audit_service,
        request_id=request_id_var.get(),
    )
    allocation = service.create(data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ALLOCATION_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="allocation",
        resource_id=str(allocation.id),
        request_id=request_id_var.get(),
    )
    return AllocationRead.model_validate(allocation)


@router.get("", response_model=Page[AllocationRead])
def list_allocations(
    person_id: uuid.UUID | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.ALLOCATION_READ)),
    service: AllocationService = Depends(get_allocation_service),
) -> Page[AllocationRead]:
    items, total = service.list(
        person_id=person_id, project_id=project_id, limit=limit, offset=offset
    )
    return Page[AllocationRead](
        items=[AllocationRead.model_validate(item) for item in items], total=total
    )


@router.get("/{allocation_id}", response_model=AllocationRead)
def get_allocation(
    allocation_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.ALLOCATION_READ)),
    service: AllocationService = Depends(get_allocation_service),
) -> AllocationRead:
    return AllocationRead.model_validate(service.get(allocation_id))


@router.patch(
    "/{allocation_id}", response_model=AllocationRead, dependencies=[Depends(require_csrf)]
)
def update_allocation(
    allocation_id: uuid.UUID,
    data: AllocationUpdate,
    current_user: User = Depends(require_permission(Permission.ALLOCATION_WRITE)),
    service: AllocationService = Depends(get_allocation_service),
    audit_service: AuditService = Depends(get_audit_service),
    access_grants: AccessGrantService = Depends(get_access_grant_service),
) -> AllocationRead:
    # AllocationUpdate has no project_id field (an allocation can't be
    # re-pointed to a different project), so scope is resolved from the
    # EXISTING row, fetched before mutating.
    existing = service.get(allocation_id)
    access_grants.enforce_project_access(
        current_user,
        existing.project_id,
        Permission.ALLOCATION_WRITE,
        audit_service=audit_service,
        request_id=request_id_var.get(),
    )
    allocation = service.update(allocation_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ALLOCATION_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="allocation",
        resource_id=str(allocation.id),
        request_id=request_id_var.get(),
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return AllocationRead.model_validate(allocation)


@router.delete(
    "/{allocation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_allocation(
    allocation_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.ALLOCATION_DELETE)),
    service: AllocationService = Depends(get_allocation_service),
    audit_service: AuditService = Depends(get_audit_service),
    access_grants: AccessGrantService = Depends(get_access_grant_service),
) -> None:
    existing = service.get(allocation_id)
    access_grants.enforce_project_access(
        current_user,
        existing.project_id,
        Permission.ALLOCATION_DELETE,
        audit_service=audit_service,
        request_id=request_id_var.get(),
    )
    service.delete(allocation_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ALLOCATION_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="allocation",
        resource_id=str(allocation_id),
        request_id=request_id_var.get(),
    )

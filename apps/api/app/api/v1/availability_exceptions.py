import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_audit_service, get_current_membership, require_csrf, require_permission
from app.core.database import get_db
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.schemas.availability_exception import (
    AvailabilityExceptionCreate,
    AvailabilityExceptionRead,
    AvailabilityExceptionUpdate,
)
from app.schemas.common import Page
from app.services.audit import AuditService
from app.services.availability_exception import AvailabilityExceptionService

router = APIRouter(prefix="/api/v1/availability-exceptions", tags=["availability-exceptions"])


def get_availability_exception_service(
    db: Session = Depends(get_db),
) -> AvailabilityExceptionService:
    return AvailabilityExceptionService(AvailabilityExceptionRepository(db), PersonRepository(db))


@router.post(
    "", response_model=AvailabilityExceptionRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_availability_exception(
    data: AvailabilityExceptionCreate,
    current_user: User = Depends(require_permission(Permission.SCHEDULE_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: AvailabilityExceptionService = Depends(get_availability_exception_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> AvailabilityExceptionRead:
    exception = service.create(membership.organization_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.AVAILABILITY_EXCEPTION_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="availability_exception",
        resource_id=str(exception.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )
    return AvailabilityExceptionRead.model_validate(exception)


@router.get("", response_model=Page[AvailabilityExceptionRead])
def list_availability_exceptions(
    person_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.SCHEDULE_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: AvailabilityExceptionService = Depends(get_availability_exception_service),
) -> Page[AvailabilityExceptionRead]:
    items, total = service.list(
        membership.organization_id, person_id=person_id, limit=limit, offset=offset
    )
    return Page[AvailabilityExceptionRead](
        items=[AvailabilityExceptionRead.model_validate(item) for item in items], total=total
    )


@router.get("/{exception_id}", response_model=AvailabilityExceptionRead)
def get_availability_exception(
    exception_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.SCHEDULE_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: AvailabilityExceptionService = Depends(get_availability_exception_service),
) -> AvailabilityExceptionRead:
    return AvailabilityExceptionRead.model_validate(
        service.get(membership.organization_id, exception_id)
    )


@router.patch(
    "/{exception_id}",
    response_model=AvailabilityExceptionRead,
    dependencies=[Depends(require_csrf)],
)
def update_availability_exception(
    exception_id: uuid.UUID,
    data: AvailabilityExceptionUpdate,
    current_user: User = Depends(require_permission(Permission.SCHEDULE_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: AvailabilityExceptionService = Depends(get_availability_exception_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> AvailabilityExceptionRead:
    exception = service.update(membership.organization_id, exception_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.AVAILABILITY_EXCEPTION_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="availability_exception",
        resource_id=str(exception.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )
    return AvailabilityExceptionRead.model_validate(exception)


@router.delete(
    "/{exception_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
def delete_availability_exception(
    exception_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.SCHEDULE_DELETE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: AvailabilityExceptionService = Depends(get_availability_exception_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete(membership.organization_id, exception_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.AVAILABILITY_EXCEPTION_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="availability_exception",
        resource_id=str(exception_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )

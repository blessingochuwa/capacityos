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
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.working_schedule import (
    WorkingScheduleCreate,
    WorkingScheduleRead,
    WorkingScheduleUpdate,
)
from app.services.audit import AuditService
from app.services.working_schedule import WorkingScheduleService

router = APIRouter(prefix="/api/v1/working-schedules", tags=["working-schedules"])


def get_working_schedule_service(db: Session = Depends(get_db)) -> WorkingScheduleService:
    return WorkingScheduleService(WorkingScheduleRepository(db), PersonRepository(db))


@router.post(
    "", response_model=WorkingScheduleRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_working_schedule(
    data: WorkingScheduleCreate,
    current_user: User = Depends(require_permission(Permission.SCHEDULE_WRITE)),
    service: WorkingScheduleService = Depends(get_working_schedule_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> WorkingScheduleRead:
    schedule = service.create(data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.WORKING_SCHEDULE_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="working_schedule",
        resource_id=str(schedule.id),
        request_id=request_id_var.get(),
    )
    return WorkingScheduleRead.model_validate(schedule)


@router.get("", response_model=list[WorkingScheduleRead])
def list_working_schedules(
    person_id: uuid.UUID = Query(),
    _: User = Depends(require_permission(Permission.SCHEDULE_READ)),
    service: WorkingScheduleService = Depends(get_working_schedule_service),
) -> list[WorkingScheduleRead]:
    return [
        WorkingScheduleRead.model_validate(item) for item in service.list_for_person(person_id)
    ]


@router.get("/{schedule_id}", response_model=WorkingScheduleRead)
def get_working_schedule(
    schedule_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.SCHEDULE_READ)),
    service: WorkingScheduleService = Depends(get_working_schedule_service),
) -> WorkingScheduleRead:
    return WorkingScheduleRead.model_validate(service.get(schedule_id))


@router.patch(
    "/{schedule_id}", response_model=WorkingScheduleRead, dependencies=[Depends(require_csrf)]
)
def update_working_schedule(
    schedule_id: uuid.UUID,
    data: WorkingScheduleUpdate,
    current_user: User = Depends(require_permission(Permission.SCHEDULE_WRITE)),
    service: WorkingScheduleService = Depends(get_working_schedule_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> WorkingScheduleRead:
    schedule = service.update(schedule_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.WORKING_SCHEDULE_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="working_schedule",
        resource_id=str(schedule.id),
        request_id=request_id_var.get(),
    )
    return WorkingScheduleRead.model_validate(schedule)


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_working_schedule(
    schedule_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.SCHEDULE_DELETE)),
    service: WorkingScheduleService = Depends(get_working_schedule_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete(schedule_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.WORKING_SCHEDULE_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="working_schedule",
        resource_id=str(schedule_id),
        request_id=request_id_var.get(),
    )

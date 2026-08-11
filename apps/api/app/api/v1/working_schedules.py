import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.person import PersonRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.working_schedule import (
    WorkingScheduleCreate,
    WorkingScheduleRead,
    WorkingScheduleUpdate,
)
from app.services.working_schedule import WorkingScheduleService

router = APIRouter(prefix="/api/v1/working-schedules", tags=["working-schedules"])


def get_working_schedule_service(db: Session = Depends(get_db)) -> WorkingScheduleService:
    return WorkingScheduleService(WorkingScheduleRepository(db), PersonRepository(db))


@router.post("", response_model=WorkingScheduleRead, status_code=status.HTTP_201_CREATED)
def create_working_schedule(
    data: WorkingScheduleCreate,
    service: WorkingScheduleService = Depends(get_working_schedule_service),
) -> WorkingScheduleRead:
    return WorkingScheduleRead.model_validate(service.create(data))


@router.get("", response_model=list[WorkingScheduleRead])
def list_working_schedules(
    person_id: uuid.UUID = Query(),
    service: WorkingScheduleService = Depends(get_working_schedule_service),
) -> list[WorkingScheduleRead]:
    return [
        WorkingScheduleRead.model_validate(item) for item in service.list_for_person(person_id)
    ]


@router.get("/{schedule_id}", response_model=WorkingScheduleRead)
def get_working_schedule(
    schedule_id: uuid.UUID,
    service: WorkingScheduleService = Depends(get_working_schedule_service),
) -> WorkingScheduleRead:
    return WorkingScheduleRead.model_validate(service.get(schedule_id))


@router.patch("/{schedule_id}", response_model=WorkingScheduleRead)
def update_working_schedule(
    schedule_id: uuid.UUID,
    data: WorkingScheduleUpdate,
    service: WorkingScheduleService = Depends(get_working_schedule_service),
) -> WorkingScheduleRead:
    return WorkingScheduleRead.model_validate(service.update(schedule_id, data))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_working_schedule(
    schedule_id: uuid.UUID,
    service: WorkingScheduleService = Depends(get_working_schedule_service),
) -> None:
    service.delete(schedule_id)

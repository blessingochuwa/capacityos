import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.schemas.availability_exception import (
    AvailabilityExceptionCreate,
    AvailabilityExceptionRead,
    AvailabilityExceptionUpdate,
)
from app.schemas.common import Page
from app.services.availability_exception import AvailabilityExceptionService

router = APIRouter(prefix="/api/v1/availability-exceptions", tags=["availability-exceptions"])


def get_availability_exception_service(
    db: Session = Depends(get_db),
) -> AvailabilityExceptionService:
    return AvailabilityExceptionService(AvailabilityExceptionRepository(db), PersonRepository(db))


@router.post("", response_model=AvailabilityExceptionRead, status_code=status.HTTP_201_CREATED)
def create_availability_exception(
    data: AvailabilityExceptionCreate,
    service: AvailabilityExceptionService = Depends(get_availability_exception_service),
) -> AvailabilityExceptionRead:
    return AvailabilityExceptionRead.model_validate(service.create(data))


@router.get("", response_model=Page[AvailabilityExceptionRead])
def list_availability_exceptions(
    person_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: AvailabilityExceptionService = Depends(get_availability_exception_service),
) -> Page[AvailabilityExceptionRead]:
    items, total = service.list(person_id=person_id, limit=limit, offset=offset)
    return Page[AvailabilityExceptionRead](
        items=[AvailabilityExceptionRead.model_validate(item) for item in items], total=total
    )


@router.get("/{exception_id}", response_model=AvailabilityExceptionRead)
def get_availability_exception(
    exception_id: uuid.UUID,
    service: AvailabilityExceptionService = Depends(get_availability_exception_service),
) -> AvailabilityExceptionRead:
    return AvailabilityExceptionRead.model_validate(service.get(exception_id))


@router.patch("/{exception_id}", response_model=AvailabilityExceptionRead)
def update_availability_exception(
    exception_id: uuid.UUID,
    data: AvailabilityExceptionUpdate,
    service: AvailabilityExceptionService = Depends(get_availability_exception_service),
) -> AvailabilityExceptionRead:
    return AvailabilityExceptionRead.model_validate(service.update(exception_id, data))


@router.delete("/{exception_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_availability_exception(
    exception_id: uuid.UUID,
    service: AvailabilityExceptionService = Depends(get_availability_exception_service),
) -> None:
    service.delete(exception_id)

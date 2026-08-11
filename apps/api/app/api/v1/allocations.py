import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.allocation import AllocationRepository
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.schemas.allocation import AllocationCreate, AllocationRead, AllocationUpdate
from app.schemas.common import Page
from app.services.allocation import AllocationService

router = APIRouter(prefix="/api/v1/allocations", tags=["allocations"])


def get_allocation_service(db: Session = Depends(get_db)) -> AllocationService:
    return AllocationService(
        AllocationRepository(db), PersonRepository(db), ProjectRepository(db)
    )


@router.post("", response_model=AllocationRead, status_code=status.HTTP_201_CREATED)
def create_allocation(
    data: AllocationCreate, service: AllocationService = Depends(get_allocation_service)
) -> AllocationRead:
    return AllocationRead.model_validate(service.create(data))


@router.get("", response_model=Page[AllocationRead])
def list_allocations(
    person_id: uuid.UUID | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
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
    allocation_id: uuid.UUID, service: AllocationService = Depends(get_allocation_service)
) -> AllocationRead:
    return AllocationRead.model_validate(service.get(allocation_id))


@router.patch("/{allocation_id}", response_model=AllocationRead)
def update_allocation(
    allocation_id: uuid.UUID,
    data: AllocationUpdate,
    service: AllocationService = Depends(get_allocation_service),
) -> AllocationRead:
    return AllocationRead.model_validate(service.update(allocation_id, data))


@router.delete("/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allocation(
    allocation_id: uuid.UUID, service: AllocationService = Depends(get_allocation_service)
) -> None:
    service.delete(allocation_id)

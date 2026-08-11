import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.person import PersonRepository
from app.schemas.common import Page
from app.schemas.person import PersonCreate, PersonRead, PersonUpdate
from app.services.person import PersonService

router = APIRouter(prefix="/api/v1/people", tags=["people"])


def get_person_service(db: Session = Depends(get_db)) -> PersonService:
    return PersonService(PersonRepository(db))


@router.post("", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
def create_person(
    data: PersonCreate, service: PersonService = Depends(get_person_service)
) -> PersonRead:
    return PersonRead.model_validate(service.create(data))


@router.get("", response_model=Page[PersonRead])
def list_people(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: PersonService = Depends(get_person_service),
) -> Page[PersonRead]:
    items, total = service.list(limit=limit, offset=offset)
    return Page[PersonRead](items=[PersonRead.model_validate(item) for item in items], total=total)


@router.get("/{person_id}", response_model=PersonRead)
def get_person(
    person_id: uuid.UUID, service: PersonService = Depends(get_person_service)
) -> PersonRead:
    return PersonRead.model_validate(service.get(person_id))


@router.patch("/{person_id}", response_model=PersonRead)
def update_person(
    person_id: uuid.UUID,
    data: PersonUpdate,
    service: PersonService = Depends(get_person_service),
) -> PersonRead:
    return PersonRead.model_validate(service.update(person_id, data))


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(
    person_id: uuid.UUID, service: PersonService = Depends(get_person_service)
) -> None:
    service.delete(person_id)

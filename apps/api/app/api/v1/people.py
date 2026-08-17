import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.skill import SkillRepository
from app.schemas.common import Page
from app.schemas.person import PersonCreate, PersonRead, PersonUpdate
from app.schemas.person_skill import PersonSkillCreate, PersonSkillRead, PersonSkillUpdate
from app.services.person import PersonService
from app.services.person_skill import PersonSkillService

router = APIRouter(prefix="/api/v1/people", tags=["people"])


def get_person_service(db: Session = Depends(get_db)) -> PersonService:
    return PersonService(PersonRepository(db))


def get_person_skill_service(db: Session = Depends(get_db)) -> PersonSkillService:
    return PersonSkillService(PersonSkillRepository(db), PersonRepository(db), SkillRepository(db))


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


@router.get("/{person_id}/skills", response_model=list[PersonSkillRead])
def list_person_skills(
    person_id: uuid.UUID, service: PersonSkillService = Depends(get_person_skill_service)
) -> list[PersonSkillRead]:
    return [PersonSkillRead.model_validate(row) for row in service.list_for_person(person_id)]


@router.post(
    "/{person_id}/skills", response_model=PersonSkillRead, status_code=status.HTTP_201_CREATED
)
def add_person_skill(
    person_id: uuid.UUID,
    data: PersonSkillCreate,
    service: PersonSkillService = Depends(get_person_skill_service),
) -> PersonSkillRead:
    return PersonSkillRead.model_validate(service.add(person_id, data))


@router.patch("/{person_id}/skills/{person_skill_id}", response_model=PersonSkillRead)
def update_person_skill(
    person_id: uuid.UUID,
    person_skill_id: uuid.UUID,
    data: PersonSkillUpdate,
    service: PersonSkillService = Depends(get_person_skill_service),
) -> PersonSkillRead:
    return PersonSkillRead.model_validate(service.update(person_id, person_skill_id, data))


@router.delete("/{person_id}/skills/{person_skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_person_skill(
    person_id: uuid.UUID,
    person_skill_id: uuid.UUID,
    service: PersonSkillService = Depends(get_person_skill_service),
) -> None:
    service.remove(person_id, person_skill_id)

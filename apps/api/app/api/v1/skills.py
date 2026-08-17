import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.skill import SkillRepository
from app.schemas.common import Page
from app.schemas.skill import SkillCreate, SkillRead, SkillUpdate
from app.services.skill import SkillService

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


def get_skill_service(db: Session = Depends(get_db)) -> SkillService:
    return SkillService(SkillRepository(db))


@router.post("", response_model=SkillRead, status_code=status.HTTP_201_CREATED)
def create_skill(
    data: SkillCreate, service: SkillService = Depends(get_skill_service)
) -> SkillRead:
    skill = service.create(data)
    return service.get_read(skill.id)


@router.get("", response_model=Page[SkillRead])
def list_skills(
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SkillService = Depends(get_skill_service),
) -> Page[SkillRead]:
    items, total = service.list(is_active=is_active, limit=limit, offset=offset)
    return Page[SkillRead](items=items, total=total)


@router.get("/{skill_id}", response_model=SkillRead)
def get_skill(
    skill_id: uuid.UUID, service: SkillService = Depends(get_skill_service)
) -> SkillRead:
    return service.get_read(skill_id)


@router.patch("/{skill_id}", response_model=SkillRead)
def update_skill(
    skill_id: uuid.UUID,
    data: SkillUpdate,
    service: SkillService = Depends(get_skill_service),
) -> SkillRead:
    service.update(skill_id, data)
    return service.get_read(skill_id)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_skill(
    skill_id: uuid.UUID, service: SkillService = Depends(get_skill_service)
) -> None:
    """Deactivates (soft-deletes) the skill — see Skill's docstring for why
    this is not a hard DELETE."""
    service.deactivate(skill_id)

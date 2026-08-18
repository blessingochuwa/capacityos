import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_audit_service, require_csrf, require_permission
from app.core.database import get_db
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome
from app.models.user import User
from app.repositories.skill import SkillRepository
from app.schemas.common import Page
from app.schemas.skill import SkillCreate, SkillRead, SkillUpdate
from app.services.audit import AuditService
from app.services.skill import SkillService

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


def get_skill_service(db: Session = Depends(get_db)) -> SkillService:
    return SkillService(SkillRepository(db))


@router.post(
    "", response_model=SkillRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_skill(
    data: SkillCreate,
    current_user: User = Depends(require_permission(Permission.SKILL_WRITE)),
    service: SkillService = Depends(get_skill_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> SkillRead:
    skill = service.create(data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.SKILL_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="skill",
        resource_id=str(skill.id),
        request_id=request_id_var.get(),
    )
    return service.get_read(skill.id)


@router.get("", response_model=Page[SkillRead])
def list_skills(
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.SKILL_READ)),
    service: SkillService = Depends(get_skill_service),
) -> Page[SkillRead]:
    items, total = service.list(is_active=is_active, limit=limit, offset=offset)
    return Page[SkillRead](items=items, total=total)


@router.get("/{skill_id}", response_model=SkillRead)
def get_skill(
    skill_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.SKILL_READ)),
    service: SkillService = Depends(get_skill_service),
) -> SkillRead:
    return service.get_read(skill_id)


@router.patch("/{skill_id}", response_model=SkillRead, dependencies=[Depends(require_csrf)])
def update_skill(
    skill_id: uuid.UUID,
    data: SkillUpdate,
    current_user: User = Depends(require_permission(Permission.SKILL_WRITE)),
    service: SkillService = Depends(get_skill_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> SkillRead:
    service.update(skill_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.SKILL_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="skill",
        resource_id=str(skill_id),
        request_id=request_id_var.get(),
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return service.get_read(skill_id)


@router.delete(
    "/{skill_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
def deactivate_skill(
    skill_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.SKILL_DELETE)),
    service: SkillService = Depends(get_skill_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    """Deactivates (soft-deletes) the skill — see Skill's docstring for why
    this is not a hard DELETE."""
    service.deactivate(skill_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.SKILL_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="skill",
        resource_id=str(skill_id),
        request_id=request_id_var.get(),
    )

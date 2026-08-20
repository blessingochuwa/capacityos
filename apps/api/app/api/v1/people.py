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
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.skill import SkillRepository
from app.schemas.common import Page
from app.schemas.person import PersonCreate, PersonRead, PersonUpdate
from app.schemas.person_skill import PersonSkillCreate, PersonSkillRead, PersonSkillUpdate
from app.services.audit import AuditService
from app.services.person import PersonService
from app.services.person_skill import PersonSkillService

router = APIRouter(prefix="/api/v1/people", tags=["people"])


def get_person_service(db: Session = Depends(get_db)) -> PersonService:
    return PersonService(PersonRepository(db))


def get_person_skill_service(db: Session = Depends(get_db)) -> PersonSkillService:
    return PersonSkillService(PersonSkillRepository(db), PersonRepository(db), SkillRepository(db))


@router.post(
    "", response_model=PersonRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_person(
    data: PersonCreate,
    current_user: User = Depends(require_permission(Permission.PERSON_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PersonService = Depends(get_person_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> PersonRead:
    person = service.create(membership.organization_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PERSON_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="person",
        resource_id=str(person.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )
    return PersonRead.model_validate(person)


@router.get("", response_model=Page[PersonRead])
def list_people(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.PERSON_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PersonService = Depends(get_person_service),
) -> Page[PersonRead]:
    items, total = service.list(membership.organization_id, limit=limit, offset=offset)
    return Page[PersonRead](items=[PersonRead.model_validate(item) for item in items], total=total)


@router.get("/{person_id}", response_model=PersonRead)
def get_person(
    person_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.PERSON_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PersonService = Depends(get_person_service),
) -> PersonRead:
    return PersonRead.model_validate(service.get(membership.organization_id, person_id))


@router.patch("/{person_id}", response_model=PersonRead, dependencies=[Depends(require_csrf)])
def update_person(
    person_id: uuid.UUID,
    data: PersonUpdate,
    current_user: User = Depends(require_permission(Permission.PERSON_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PersonService = Depends(get_person_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> PersonRead:
    person = service.update(membership.organization_id, person_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PERSON_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="person",
        resource_id=str(person.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return PersonRead.model_validate(person)


@router.delete(
    "/{person_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
def delete_person(
    person_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.PERSON_DELETE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PersonService = Depends(get_person_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete(membership.organization_id, person_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PERSON_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="person",
        resource_id=str(person_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )


@router.get("/{person_id}/skills", response_model=list[PersonSkillRead])
def list_person_skills(
    person_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.SKILL_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PersonSkillService = Depends(get_person_skill_service),
) -> list[PersonSkillRead]:
    return [
        PersonSkillRead.model_validate(row)
        for row in service.list_for_person(membership.organization_id, person_id)
    ]


@router.post(
    "/{person_id}/skills", response_model=PersonSkillRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def add_person_skill(
    person_id: uuid.UUID,
    data: PersonSkillCreate,
    current_user: User = Depends(require_permission(Permission.SKILL_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PersonSkillService = Depends(get_person_skill_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> PersonSkillRead:
    person_skill = service.add(membership.organization_id, person_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PERSON_SKILL_ADD,
        outcome=AuditOutcome.SUCCESS,
        resource_type="person_skill",
        resource_id=str(person_skill.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"person_id": str(person_id), "skill_id": str(data.skill_id)},
    )
    return PersonSkillRead.model_validate(person_skill)


@router.patch(
    "/{person_id}/skills/{person_skill_id}", response_model=PersonSkillRead,
    dependencies=[Depends(require_csrf)],
)
def update_person_skill(
    person_id: uuid.UUID,
    person_skill_id: uuid.UUID,
    data: PersonSkillUpdate,
    current_user: User = Depends(require_permission(Permission.SKILL_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PersonSkillService = Depends(get_person_skill_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> PersonSkillRead:
    person_skill = service.update(membership.organization_id, person_id, person_skill_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PERSON_SKILL_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="person_skill",
        resource_id=str(person_skill_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )
    return PersonSkillRead.model_validate(person_skill)


@router.delete(
    "/{person_id}/skills/{person_skill_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def remove_person_skill(
    person_id: uuid.UUID,
    person_skill_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.SKILL_DELETE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PersonSkillService = Depends(get_person_skill_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.remove(membership.organization_id, person_id, person_skill_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PERSON_SKILL_REMOVE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="person_skill",
        resource_id=str(person_skill_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )

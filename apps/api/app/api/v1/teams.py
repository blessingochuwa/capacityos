import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_audit_service, require_csrf, require_permission
from app.core.database import get_db
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome
from app.models.user import User
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_skill_requirement import ProjectSkillRequirementRepository
from app.repositories.skill import SkillRepository
from app.repositories.team import TeamRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.common import Page
from app.schemas.skill_capacity import TeamSkillCapacityRead
from app.schemas.team import TeamCreate, TeamRead, TeamUpdate
from app.schemas.team_membership import TeamMembershipCreate, TeamMembershipRead
from app.services.audit import AuditService
from app.services.skill_capacity import SkillCapacityService
from app.services.team import TeamService
from app.services.team_membership import TeamMembershipService

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


def get_team_service(db: Session = Depends(get_db)) -> TeamService:
    return TeamService(TeamRepository(db))


def get_team_membership_service(db: Session = Depends(get_db)) -> TeamMembershipService:
    return TeamMembershipService(
        TeamMembershipRepository(db), PersonRepository(db), TeamRepository(db)
    )


def get_skill_capacity_service(db: Session = Depends(get_db)) -> SkillCapacityService:
    return SkillCapacityService(
        PersonSkillRepository(db),
        SkillRepository(db),
        PersonRepository(db),
        ProjectRepository(db),
        ProjectSkillRequirementRepository(db),
        TeamRepository(db),
        TeamMembershipRepository(db),
        WorkingScheduleRepository(db),
        AvailabilityExceptionRepository(db),
        AllocationRepository(db),
    )


@router.post(
    "", response_model=TeamRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_team(
    data: TeamCreate,
    current_user: User = Depends(require_permission(Permission.TEAM_WRITE)),
    service: TeamService = Depends(get_team_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> TeamRead:
    team = service.create(data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.TEAM_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="team",
        resource_id=str(team.id),
        request_id=request_id_var.get(),
    )
    return TeamRead.model_validate(team)


@router.get("", response_model=Page[TeamRead])
def list_teams(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.TEAM_READ)),
    service: TeamService = Depends(get_team_service),
) -> Page[TeamRead]:
    items, total = service.list(limit=limit, offset=offset)
    return Page[TeamRead](items=[TeamRead.model_validate(item) for item in items], total=total)


@router.get("/{team_id}", response_model=TeamRead)
def get_team(
    team_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.TEAM_READ)),
    service: TeamService = Depends(get_team_service),
) -> TeamRead:
    return TeamRead.model_validate(service.get(team_id))


@router.patch("/{team_id}", response_model=TeamRead, dependencies=[Depends(require_csrf)])
def update_team(
    team_id: uuid.UUID,
    data: TeamUpdate,
    current_user: User = Depends(require_permission(Permission.TEAM_WRITE)),
    service: TeamService = Depends(get_team_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> TeamRead:
    team = service.update(team_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.TEAM_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="team",
        resource_id=str(team.id),
        request_id=request_id_var.get(),
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return TeamRead.model_validate(team)


@router.delete(
    "/{team_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
def delete_team(
    team_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.TEAM_DELETE)),
    service: TeamService = Depends(get_team_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete(team_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.TEAM_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="team",
        resource_id=str(team_id),
        request_id=request_id_var.get(),
    )


@router.get("/{team_id}/members", response_model=list[TeamMembershipRead])
def list_team_members(
    team_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.TEAM_READ)),
    service: TeamMembershipService = Depends(get_team_membership_service),
) -> list[TeamMembershipRead]:
    return [TeamMembershipRead.model_validate(m) for m in service.list_members(team_id)]


@router.post(
    "/{team_id}/members", response_model=TeamMembershipRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def add_team_member(
    team_id: uuid.UUID,
    data: TeamMembershipCreate,
    current_user: User = Depends(require_permission(Permission.TEAM_WRITE)),
    service: TeamMembershipService = Depends(get_team_membership_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> TeamMembershipRead:
    membership = service.add_member(team_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.TEAM_MEMBER_ADD,
        outcome=AuditOutcome.SUCCESS,
        resource_type="team",
        resource_id=str(team_id),
        request_id=request_id_var.get(),
        metadata={"person_id": str(data.person_id)},
    )
    return TeamMembershipRead.model_validate(membership)


@router.delete(
    "/{team_id}/members/{person_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def remove_team_member(
    team_id: uuid.UUID,
    person_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.TEAM_DELETE)),
    service: TeamMembershipService = Depends(get_team_membership_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.remove_member(team_id, person_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.TEAM_MEMBER_REMOVE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="team",
        resource_id=str(team_id),
        request_id=request_id_var.get(),
        metadata={"person_id": str(person_id)},
    )


@router.get("/{team_id}/skill-capacity", response_model=TeamSkillCapacityRead)
def get_team_skill_capacity(
    team_id: uuid.UUID,
    start_date: date,
    end_date: date,
    _: User = Depends(require_permission(Permission.SKILL_READ)),
    service: SkillCapacityService = Depends(get_skill_capacity_service),
) -> TeamSkillCapacityRead:
    return service.get_team_skill_capacity(team_id, start_date, end_date)

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_audit_service,
    get_current_membership,
    require_csrf,
    require_permission,
    require_project_access,
)
from app.core.database import get_db
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_skill_requirement import ProjectSkillRequirementRepository
from app.repositories.risk import RiskRepository
from app.repositories.skill import SkillRepository
from app.repositories.stakeholder import StakeholderRepository
from app.repositories.team import TeamRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.common import Page
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.project_skill_requirement import (
    ProjectSkillRequirementCreate,
    ProjectSkillRequirementRead,
    ProjectSkillRequirementUpdate,
)
from app.schemas.risk import RiskCreate, RiskRead, RiskUpdate, risk_to_read
from app.schemas.skill_capacity import ProjectSkillCoverageRead
from app.schemas.stakeholder import StakeholderCreate, StakeholderRead, StakeholderUpdate
from app.services.audit import AuditService
from app.services.project import ProjectService
from app.services.project_skill_requirement import ProjectSkillRequirementService
from app.services.risk import RiskService
from app.services.skill_capacity import SkillCapacityService
from app.services.stakeholder import StakeholderService

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(ProjectRepository(db))


def get_project_skill_requirement_service(
    db: Session = Depends(get_db),
) -> ProjectSkillRequirementService:
    return ProjectSkillRequirementService(
        ProjectSkillRequirementRepository(db), ProjectRepository(db), SkillRepository(db)
    )


def get_risk_service(db: Session = Depends(get_db)) -> RiskService:
    return RiskService(RiskRepository(db), ProjectRepository(db), PersonRepository(db))


def get_stakeholder_service(db: Session = Depends(get_db)) -> StakeholderService:
    return StakeholderService(
        StakeholderRepository(db), ProjectRepository(db), PersonRepository(db)
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
    "", response_model=ProjectRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_project(
    data: ProjectCreate,
    current_user: User = Depends(require_permission(Permission.PROJECT_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectService = Depends(get_project_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ProjectRead:
    project = service.create(membership.organization_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project",
        resource_id=str(project.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )
    return ProjectRead.model_validate(project)


@router.get("", response_model=Page[ProjectRead])
def list_projects(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.PROJECT_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectService = Depends(get_project_service),
) -> Page[ProjectRead]:
    items, total = service.list(membership.organization_id, limit=limit, offset=offset)
    return Page[ProjectRead](
        items=[ProjectRead.model_validate(item) for item in items], total=total
    )


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.PROJECT_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    return ProjectRead.model_validate(service.get(membership.organization_id, project_id))


@router.patch("/{project_id}", response_model=ProjectRead, dependencies=[Depends(require_csrf)])
def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    current_user: User = Depends(require_project_access(Permission.PROJECT_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectService = Depends(get_project_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ProjectRead:
    project = service.update(membership.organization_id, project_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project",
        resource_id=str(project.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return ProjectRead.model_validate(project)


@router.delete(
    "/{project_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(require_project_access(Permission.PROJECT_DELETE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectService = Depends(get_project_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete(membership.organization_id, project_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project",
        resource_id=str(project_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )


@router.get(
    "/{project_id}/skill-requirements", response_model=list[ProjectSkillRequirementRead]
)
def list_project_skill_requirements(
    project_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.SKILL_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectSkillRequirementService = Depends(get_project_skill_requirement_service),
) -> list[ProjectSkillRequirementRead]:
    return [
        ProjectSkillRequirementRead.model_validate(row)
        for row in service.list_for_project(membership.organization_id, project_id)
    ]


@router.post(
    "/{project_id}/skill-requirements",
    response_model=ProjectSkillRequirementRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def add_project_skill_requirement(
    project_id: uuid.UUID,
    data: ProjectSkillRequirementCreate,
    current_user: User = Depends(require_project_access(Permission.SKILL_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectSkillRequirementService = Depends(get_project_skill_requirement_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ProjectSkillRequirementRead:
    requirement = service.add(membership.organization_id, project_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_SKILL_REQUIREMENT_ADD,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project_skill_requirement",
        resource_id=str(requirement.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"project_id": str(project_id), "skill_id": str(data.skill_id)},
    )
    return ProjectSkillRequirementRead.model_validate(requirement)


@router.patch(
    "/{project_id}/skill-requirements/{requirement_id}",
    response_model=ProjectSkillRequirementRead,
    dependencies=[Depends(require_csrf)],
)
def update_project_skill_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    data: ProjectSkillRequirementUpdate,
    current_user: User = Depends(require_project_access(Permission.SKILL_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectSkillRequirementService = Depends(get_project_skill_requirement_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ProjectSkillRequirementRead:
    requirement = service.update(membership.organization_id, project_id, requirement_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_SKILL_REQUIREMENT_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project_skill_requirement",
        resource_id=str(requirement_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )
    return ProjectSkillRequirementRead.model_validate(requirement)


@router.delete(
    "/{project_id}/skill-requirements/{requirement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def remove_project_skill_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: User = Depends(require_project_access(Permission.SKILL_DELETE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectSkillRequirementService = Depends(get_project_skill_requirement_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.remove(membership.organization_id, project_id, requirement_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_SKILL_REQUIREMENT_REMOVE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project_skill_requirement",
        resource_id=str(requirement_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )


@router.get("/{project_id}/skill-coverage", response_model=ProjectSkillCoverageRead)
def get_project_skill_coverage(
    project_id: uuid.UUID,
    start_date: date,
    end_date: date,
    _: User = Depends(require_permission(Permission.SKILL_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: SkillCapacityService = Depends(get_skill_capacity_service),
) -> ProjectSkillCoverageRead:
    return service.get_project_skill_coverage(
        membership.organization_id, project_id, start_date, end_date
    )


# ---------------------------------------------------------------------------
# Risks (Phase 13, CLAUDE.md §17)
# ---------------------------------------------------------------------------


@router.get("/{project_id}/risks", response_model=list[RiskRead])
def list_project_risks(
    project_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.RISK_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: RiskService = Depends(get_risk_service),
) -> list[RiskRead]:
    return [
        risk_to_read(risk)
        for risk in service.list_for_project(membership.organization_id, project_id)
    ]


@router.post(
    "/{project_id}/risks",
    response_model=RiskRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_project_risk(
    project_id: uuid.UUID,
    data: RiskCreate,
    current_user: User = Depends(require_project_access(Permission.RISK_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: RiskService = Depends(get_risk_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> RiskRead:
    risk = service.create(membership.organization_id, project_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.RISK_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="risk",
        resource_id=str(risk.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"project_id": str(project_id)},
    )
    return risk_to_read(risk)


@router.patch(
    "/{project_id}/risks/{risk_id}", response_model=RiskRead, dependencies=[Depends(require_csrf)]
)
def update_project_risk(
    project_id: uuid.UUID,
    risk_id: uuid.UUID,
    data: RiskUpdate,
    current_user: User = Depends(require_project_access(Permission.RISK_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: RiskService = Depends(get_risk_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> RiskRead:
    risk = service.update(membership.organization_id, project_id, risk_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.RISK_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="risk",
        resource_id=str(risk_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return risk_to_read(risk)


@router.delete(
    "/{project_id}/risks/{risk_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_project_risk(
    project_id: uuid.UUID,
    risk_id: uuid.UUID,
    current_user: User = Depends(require_project_access(Permission.RISK_DELETE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: RiskService = Depends(get_risk_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete(membership.organization_id, project_id, risk_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.RISK_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="risk",
        resource_id=str(risk_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )


# ---------------------------------------------------------------------------
# Stakeholders (Phase 14, CLAUDE.md §16)
# ---------------------------------------------------------------------------


@router.get("/{project_id}/stakeholders", response_model=list[StakeholderRead])
def list_project_stakeholders(
    project_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.STAKEHOLDER_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: StakeholderService = Depends(get_stakeholder_service),
) -> list[StakeholderRead]:
    return [
        StakeholderRead.model_validate(stakeholder)
        for stakeholder in service.list_for_project(membership.organization_id, project_id)
    ]


@router.post(
    "/{project_id}/stakeholders",
    response_model=StakeholderRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_project_stakeholder(
    project_id: uuid.UUID,
    data: StakeholderCreate,
    current_user: User = Depends(require_project_access(Permission.STAKEHOLDER_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: StakeholderService = Depends(get_stakeholder_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> StakeholderRead:
    stakeholder = service.create(membership.organization_id, project_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.STAKEHOLDER_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="stakeholder",
        resource_id=str(stakeholder.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"project_id": str(project_id)},
    )
    return StakeholderRead.model_validate(stakeholder)


@router.patch(
    "/{project_id}/stakeholders/{stakeholder_id}",
    response_model=StakeholderRead,
    dependencies=[Depends(require_csrf)],
)
def update_project_stakeholder(
    project_id: uuid.UUID,
    stakeholder_id: uuid.UUID,
    data: StakeholderUpdate,
    current_user: User = Depends(require_project_access(Permission.STAKEHOLDER_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: StakeholderService = Depends(get_stakeholder_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> StakeholderRead:
    stakeholder = service.update(membership.organization_id, project_id, stakeholder_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.STAKEHOLDER_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="stakeholder",
        resource_id=str(stakeholder_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return StakeholderRead.model_validate(stakeholder)


@router.delete(
    "/{project_id}/stakeholders/{stakeholder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_project_stakeholder(
    project_id: uuid.UUID,
    stakeholder_id: uuid.UUID,
    current_user: User = Depends(require_project_access(Permission.STAKEHOLDER_DELETE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: StakeholderService = Depends(get_stakeholder_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete(membership.organization_id, project_id, stakeholder_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.STAKEHOLDER_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="stakeholder",
        resource_id=str(stakeholder_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )

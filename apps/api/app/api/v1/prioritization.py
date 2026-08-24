import uuid

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
from app.repositories.prioritization_criterion import PrioritizationCriterionRepository
from app.repositories.prioritization_framework import PrioritizationFrameworkRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_priority_score import ProjectPriorityScoreRepository
from app.schemas.common import Page
from app.schemas.prioritization import (
    PortfolioRankingEntryRead,
    PortfolioRankingRead,
    PrioritizationFrameworkCreate,
    PrioritizationFrameworkRead,
    PrioritizationFrameworkUpdate,
    ProjectPriorityScoreCreate,
    ProjectPriorityScoreRead,
    ProjectPriorityScoreUpdate,
    framework_to_read,
    project_priority_score_to_read,
)
from app.services.audit import AuditService
from app.services.prioritization_framework import PrioritizationFrameworkService
from app.services.project_priority_score import ProjectPriorityScoreService

router = APIRouter(tags=["prioritization"])


def get_framework_service(db: Session = Depends(get_db)) -> PrioritizationFrameworkService:
    return PrioritizationFrameworkService(
        PrioritizationFrameworkRepository(db), PrioritizationCriterionRepository(db)
    )


def get_score_service(db: Session = Depends(get_db)) -> ProjectPriorityScoreService:
    return ProjectPriorityScoreService(
        ProjectPriorityScoreRepository(db),
        ProjectRepository(db),
        PrioritizationFrameworkRepository(db),
    )


# ---------------------------------------------------------------------------
# Frameworks — organization-wide (no ProjectAccessGrant involved), matching
# Skill's exact catalog shape. PRIORITIZATION_MANAGE (Admin/Owner only,
# never Manager) gates every write — see Permission.PRIORITIZATION_MANAGE's
# docstring for why this is stricter than Skill's Manager-writable
# precedent.
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/prioritization/frameworks",
    response_model=PrioritizationFrameworkRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_framework(
    data: PrioritizationFrameworkCreate,
    current_user: User = Depends(require_permission(Permission.PRIORITIZATION_MANAGE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PrioritizationFrameworkService = Depends(get_framework_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> PrioritizationFrameworkRead:
    framework = service.create(membership.organization_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PRIORITIZATION_FRAMEWORK_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="prioritization_framework",
        resource_id=str(framework.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={
            "framework_type": framework.framework_type.value,
            "criteria": [
                {"name": c.name, "weight": str(c.weight) if c.weight is not None else None}
                for c in framework.criteria
            ],
        },
    )
    return framework_to_read(framework)


@router.get("/api/v1/prioritization/frameworks", response_model=Page[PrioritizationFrameworkRead])
def list_frameworks(
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.PRIORITIZATION_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PrioritizationFrameworkService = Depends(get_framework_service),
) -> Page[PrioritizationFrameworkRead]:
    items, total = service.list(
        membership.organization_id, is_active=is_active, limit=limit, offset=offset
    )
    return Page[PrioritizationFrameworkRead](
        items=[framework_to_read(item) for item in items], total=total
    )


@router.get(
    "/api/v1/prioritization/frameworks/{framework_id}", response_model=PrioritizationFrameworkRead
)
def get_framework(
    framework_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.PRIORITIZATION_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PrioritizationFrameworkService = Depends(get_framework_service),
) -> PrioritizationFrameworkRead:
    return framework_to_read(service.get(membership.organization_id, framework_id))


@router.patch(
    "/api/v1/prioritization/frameworks/{framework_id}",
    response_model=PrioritizationFrameworkRead,
    dependencies=[Depends(require_csrf)],
)
def update_framework(
    framework_id: uuid.UUID,
    data: PrioritizationFrameworkUpdate,
    current_user: User = Depends(require_permission(Permission.PRIORITIZATION_MANAGE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PrioritizationFrameworkService = Depends(get_framework_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> PrioritizationFrameworkRead:
    framework = service.update(membership.organization_id, framework_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PRIORITIZATION_FRAMEWORK_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="prioritization_framework",
        resource_id=str(framework_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return framework_to_read(framework)


@router.delete(
    "/api/v1/prioritization/frameworks/{framework_id}",
    response_model=PrioritizationFrameworkRead,
    dependencies=[Depends(require_csrf)],
)
def deactivate_framework(
    framework_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.PRIORITIZATION_MANAGE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PrioritizationFrameworkService = Depends(get_framework_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> PrioritizationFrameworkRead:
    """Soft-delete only — see PrioritizationFramework.is_active's
    docstring. Matches Skill's DELETE-means-deactivate precedent
    exactly."""
    framework = service.deactivate(membership.organization_id, framework_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PRIORITIZATION_FRAMEWORK_DEACTIVATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="prioritization_framework",
        resource_id=str(framework_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )
    return framework_to_read(framework)


@router.get("/api/v1/prioritization/portfolio", response_model=PortfolioRankingRead)
def rank_portfolio(
    framework_id: uuid.UUID = Query(),
    _: User = Depends(require_permission(Permission.PRIORITIZATION_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectPriorityScoreService = Depends(get_score_service),
) -> PortfolioRankingRead:
    framework, ranked = service.rank_portfolio(membership.organization_id, framework_id)
    items = [
        PortfolioRankingEntryRead(
            project_id=project.id,
            project_name=project.name,
            score=result.score,
            rank=rank if result.score is not None else None,
            missing_criteria=list(result.missing_criteria),
            breakdown=result.breakdown,
        )
        for rank, (project, _score, result) in enumerate(ranked, start=1)
    ]
    return PortfolioRankingRead(
        framework_id=framework.id,
        framework_name=framework.name,
        framework_type=framework.framework_type,
        items=items,
    )


# ---------------------------------------------------------------------------
# Project priority scores — nested under Project, instance-scoped via the
# existing ProjectAccessGrant mechanism exactly like Risk/Stakeholder/
# Allocation. Reads stay global per-role (Phase 11's "Manager read access
# stays global" precedent); only create/update/delete require a grant.
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/projects/{project_id}/priority-scores",
    response_model=ProjectPriorityScoreRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_project_priority_score(
    project_id: uuid.UUID,
    data: ProjectPriorityScoreCreate,
    current_user: User = Depends(require_project_access(Permission.PRIORITIZATION_SCORE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectPriorityScoreService = Depends(get_score_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ProjectPriorityScoreRead:
    score, result = service.create(membership.organization_id, project_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_PRIORITY_SCORE_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project_priority_score",
        resource_id=str(score.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"framework_id": str(score.framework_id)},
    )
    return project_priority_score_to_read(score, result)


@router.get(
    "/api/v1/projects/{project_id}/priority-scores",
    response_model=list[ProjectPriorityScoreRead],
)
def list_project_priority_scores(
    project_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.PRIORITIZATION_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectPriorityScoreService = Depends(get_score_service),
) -> list[ProjectPriorityScoreRead]:
    scores = service.list_for_project(membership.organization_id, project_id)
    return [project_priority_score_to_read(score, result) for score, result in scores]


@router.get(
    "/api/v1/projects/{project_id}/priority-scores/{score_id}",
    response_model=ProjectPriorityScoreRead,
)
def get_project_priority_score(
    project_id: uuid.UUID,
    score_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.PRIORITIZATION_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectPriorityScoreService = Depends(get_score_service),
) -> ProjectPriorityScoreRead:
    score, result = service.get(membership.organization_id, project_id, score_id)
    return project_priority_score_to_read(score, result)


@router.patch(
    "/api/v1/projects/{project_id}/priority-scores/{score_id}",
    response_model=ProjectPriorityScoreRead,
    dependencies=[Depends(require_csrf)],
)
def update_project_priority_score(
    project_id: uuid.UUID,
    score_id: uuid.UUID,
    data: ProjectPriorityScoreUpdate,
    current_user: User = Depends(require_project_access(Permission.PRIORITIZATION_SCORE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectPriorityScoreService = Depends(get_score_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ProjectPriorityScoreRead:
    score, result = service.update(membership.organization_id, project_id, score_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_PRIORITY_SCORE_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project_priority_score",
        resource_id=str(score_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return project_priority_score_to_read(score, result)


@router.delete(
    "/api/v1/projects/{project_id}/priority-scores/{score_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_project_priority_score(
    project_id: uuid.UUID,
    score_id: uuid.UUID,
    current_user: User = Depends(require_project_access(Permission.PRIORITIZATION_SCORE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectPriorityScoreService = Depends(get_score_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete(membership.organization_id, project_id, score_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_PRIORITY_SCORE_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project_priority_score",
        resource_id=str(score_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )

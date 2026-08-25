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
from app.repositories.portfolio_snapshot import PortfolioSnapshotRepository
from app.repositories.prioritization_criterion import PrioritizationCriterionRepository
from app.repositories.prioritization_framework import PrioritizationFrameworkRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_dependency import ProjectDependencyRepository
from app.repositories.project_priority_score import ProjectPriorityScoreRepository
from app.schemas.common import Page
from app.schemas.prioritization import (
    CriterionCreate,
    CriterionRead,
    CriterionUpdate,
    DependencyGraphNodeRead,
    DependencyGraphRead,
    PortfolioRankingEntryRead,
    PortfolioRankingRead,
    PortfolioSnapshotCreate,
    PortfolioSnapshotRead,
    PrioritizationFrameworkCreate,
    PrioritizationFrameworkRead,
    PrioritizationFrameworkUpdate,
    ProjectDependencyCreate,
    ProjectDependencyRead,
    ProjectPriorityScoreCreate,
    ProjectPriorityScoreRead,
    ProjectPriorityScoreUpdate,
    framework_to_read,
    portfolio_snapshot_to_read,
    project_dependency_to_read,
    project_priority_score_to_read,
)
from app.services.audit import AuditService
from app.services.portfolio_snapshot import PortfolioSnapshotService
from app.services.prioritization_framework import PrioritizationFrameworkService
from app.services.project_dependency import ProjectDependencyService
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


def get_dependency_service(db: Session = Depends(get_db)) -> ProjectDependencyService:
    return ProjectDependencyService(ProjectDependencyRepository(db), ProjectRepository(db))


def get_snapshot_service(db: Session = Depends(get_db)) -> PortfolioSnapshotService:
    return PortfolioSnapshotService(
        PortfolioSnapshotRepository(db),
        ProjectPriorityScoreService(
            ProjectPriorityScoreRepository(db),
            ProjectRepository(db),
            PrioritizationFrameworkRepository(db),
        ),
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


@router.post(
    "/api/v1/prioritization/frameworks/{framework_id}/criteria",
    response_model=CriterionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def add_criterion(
    framework_id: uuid.UUID,
    data: CriterionCreate,
    current_user: User = Depends(require_permission(Permission.PRIORITIZATION_MANAGE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PrioritizationFrameworkService = Depends(get_framework_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> CriterionRead:
    """Weighted Scoring only — see PrioritizationFrameworkService.
    add_criterion's docstring for why RICE/ICE/WSJF/MOSCOW reject this
    with 403."""
    criterion = service.add_criterion(membership.organization_id, framework_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PRIORITIZATION_CRITERION_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="prioritization_criterion",
        resource_id=str(criterion.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"framework_id": str(framework_id), "name": criterion.name},
    )
    return CriterionRead.model_validate(criterion)


@router.patch(
    "/api/v1/prioritization/frameworks/{framework_id}/criteria/{criterion_id}",
    response_model=CriterionRead,
    dependencies=[Depends(require_csrf)],
)
def update_criterion(
    framework_id: uuid.UUID,
    criterion_id: uuid.UUID,
    data: CriterionUpdate,
    current_user: User = Depends(require_permission(Permission.PRIORITIZATION_MANAGE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PrioritizationFrameworkService = Depends(get_framework_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> CriterionRead:
    criterion = service.update_criterion(
        membership.organization_id, framework_id, criterion_id, data
    )
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PRIORITIZATION_CRITERION_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="prioritization_criterion",
        resource_id=str(criterion_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return CriterionRead.model_validate(criterion)


@router.delete(
    "/api/v1/prioritization/frameworks/{framework_id}/criteria/{criterion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def remove_criterion(
    framework_id: uuid.UUID,
    criterion_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.PRIORITIZATION_MANAGE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PrioritizationFrameworkService = Depends(get_framework_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.remove_criterion(membership.organization_id, framework_id, criterion_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PRIORITIZATION_CRITERION_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="prioritization_criterion",
        resource_id=str(criterion_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"framework_id": str(framework_id)},
    )


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
            rank=rank,
            missing_criteria=list(result.missing_criteria),
            breakdown=result.breakdown,
            category=result.category,
        )
        for project, _score, result, rank in ranked
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


# ---------------------------------------------------------------------------
# Project dependencies (Phase 18) — nested under Project like priority
# scores above; gated by the same PRIORITIZATION_SCORE permission via
# require_project_access on the `from_project` side (see
# ProjectDependencyCreate's docstring for why the URL's project is always
# the owning/from side). The graph endpoint is organization-wide, gated by
# the read-only PRIORITIZATION_READ permission.
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/projects/{project_id}/dependencies",
    response_model=ProjectDependencyRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_project_dependency(
    project_id: uuid.UUID,
    data: ProjectDependencyCreate,
    current_user: User = Depends(require_project_access(Permission.PRIORITIZATION_SCORE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectDependencyService = Depends(get_dependency_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ProjectDependencyRead:
    dependency = service.create(membership.organization_id, project_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_DEPENDENCY_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project_dependency",
        resource_id=str(dependency.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={
            "to_project_id": str(dependency.to_project_id),
            "dependency_type": dependency.dependency_type.value,
        },
    )
    return project_dependency_to_read(dependency)


@router.get(
    "/api/v1/projects/{project_id}/dependencies",
    response_model=list[ProjectDependencyRead],
)
def list_project_dependencies(
    project_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.PRIORITIZATION_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectDependencyService = Depends(get_dependency_service),
) -> list[ProjectDependencyRead]:
    """Both directions — every edge where this project is either the
    `from` or `to` side (see ProjectDependencyRepository.list_for_project's
    docstring). The frontend derives "blocks"/"blocked by" from comparing
    each edge's from_project_id against this project_id itself."""
    dependencies = service.list_for_project(membership.organization_id, project_id)
    return [project_dependency_to_read(d) for d in dependencies]


@router.delete(
    "/api/v1/projects/{project_id}/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_project_dependency(
    project_id: uuid.UUID,
    dependency_id: uuid.UUID,
    current_user: User = Depends(require_project_access(Permission.PRIORITIZATION_SCORE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectDependencyService = Depends(get_dependency_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete(membership.organization_id, project_id, dependency_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PROJECT_DEPENDENCY_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project_dependency",
        resource_id=str(dependency_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )


@router.get("/api/v1/prioritization/dependency-graph", response_model=DependencyGraphRead)
def get_dependency_graph(
    _: User = Depends(require_permission(Permission.PRIORITIZATION_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ProjectDependencyService = Depends(get_dependency_service),
) -> DependencyGraphRead:
    edges = service.graph(membership.organization_id)
    nodes_by_id: dict[uuid.UUID, DependencyGraphNodeRead] = {}
    for edge in edges:
        nodes_by_id.setdefault(
            edge.from_project_id,
            DependencyGraphNodeRead(
                project_id=edge.from_project_id, project_name=edge.from_project.name
            ),
        )
        nodes_by_id.setdefault(
            edge.to_project_id,
            DependencyGraphNodeRead(
                project_id=edge.to_project_id, project_name=edge.to_project.name
            ),
        )
    return DependencyGraphRead(
        nodes=list(nodes_by_id.values()),
        edges=[project_dependency_to_read(edge) for edge in edges],
    )


# ---------------------------------------------------------------------------
# Portfolio snapshots (Phase 21) — organization-wide, like frameworks above.
# PRIORITIZATION_MANAGE (Admin/Owner only) gates creation: a snapshot spans
# every scored project under a framework, not one project a Manager might
# hold a grant on, matching framework CRUD's own "org-wide configuration
# surface" reasoning. Reads use PRIORITIZATION_READ, same as every other
# read in this router. No PATCH/DELETE route — immutable, append-only,
# matching AuditEvent's own shape.
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/prioritization/snapshots",
    response_model=PortfolioSnapshotRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_portfolio_snapshot(
    data: PortfolioSnapshotCreate,
    current_user: User = Depends(require_permission(Permission.PRIORITIZATION_MANAGE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PortfolioSnapshotService = Depends(get_snapshot_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> PortfolioSnapshotRead:
    snapshot = service.create(membership.organization_id, data.framework_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.PORTFOLIO_SNAPSHOT_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="portfolio_snapshot",
        resource_id=str(snapshot.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={
            "framework_id": str(snapshot.framework_id),
            "entry_count": len(snapshot.entries),
        },
    )
    return portfolio_snapshot_to_read(snapshot)


@router.get("/api/v1/prioritization/snapshots", response_model=Page[PortfolioSnapshotRead])
def list_portfolio_snapshots(
    framework_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.PRIORITIZATION_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: PortfolioSnapshotService = Depends(get_snapshot_service),
) -> Page[PortfolioSnapshotRead]:
    items, total = service.list(
        membership.organization_id, framework_id=framework_id, limit=limit, offset=offset
    )
    return Page[PortfolioSnapshotRead](
        items=[portfolio_snapshot_to_read(item) for item in items], total=total
    )

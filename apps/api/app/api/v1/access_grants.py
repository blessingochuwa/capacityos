import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    get_access_grant_service,
    get_audit_service,
    require_csrf,
    require_permission,
)
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome
from app.models.user import User
from app.schemas.access_grant import (
    ProjectAccessGrantCreate,
    ProjectAccessGrantRead,
    TeamAccessGrantCreate,
    TeamAccessGrantRead,
)
from app.services.access_grant import AccessGrantService
from app.services.audit import AuditService

router = APIRouter(tags=["access-grants"])
"""Instance-level resource authorization management (Phase 11). Every route
here is gated on Permission.ACCESS_MANAGE, which only Owner/Admin hold in
ROLE_PERMISSIONS — a Manager's request to this router 403s at the
type-level permission check before any resource logic runs, which is what
makes self-escalation structurally impossible (see
docs/adr/0011-instance-level-resource-authorization.md)."""


@router.get(
    "/api/v1/teams/{team_id}/access-grants", response_model=list[TeamAccessGrantRead]
)
def list_team_access_grants(
    team_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.ACCESS_MANAGE)),
    service: AccessGrantService = Depends(get_access_grant_service),
) -> list[TeamAccessGrantRead]:
    return [TeamAccessGrantRead.model_validate(g) for g in service.list_team_grants(team_id)]


@router.post(
    "/api/v1/teams/{team_id}/access-grants",
    response_model=TeamAccessGrantRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def grant_team_access(
    team_id: uuid.UUID,
    data: TeamAccessGrantCreate,
    current_user: User = Depends(require_permission(Permission.ACCESS_MANAGE)),
    service: AccessGrantService = Depends(get_access_grant_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> TeamAccessGrantRead:
    grant = service.grant_team_access(team_id, data.user_id, granted_by=current_user)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ACCESS_GRANT_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="team",
        resource_id=str(team_id),
        request_id=request_id_var.get(),
        metadata={"target_user_id": str(data.user_id)},
    )
    return TeamAccessGrantRead.model_validate(grant)


@router.delete(
    "/api/v1/teams/{team_id}/access-grants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def revoke_team_access(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.ACCESS_MANAGE)),
    service: AccessGrantService = Depends(get_access_grant_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.revoke_team_access(team_id, user_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ACCESS_GRANT_REVOKE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="team",
        resource_id=str(team_id),
        request_id=request_id_var.get(),
        metadata={"target_user_id": str(user_id)},
    )


@router.get(
    "/api/v1/projects/{project_id}/access-grants", response_model=list[ProjectAccessGrantRead]
)
def list_project_access_grants(
    project_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.ACCESS_MANAGE)),
    service: AccessGrantService = Depends(get_access_grant_service),
) -> list[ProjectAccessGrantRead]:
    return [
        ProjectAccessGrantRead.model_validate(g) for g in service.list_project_grants(project_id)
    ]


@router.post(
    "/api/v1/projects/{project_id}/access-grants",
    response_model=ProjectAccessGrantRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def grant_project_access(
    project_id: uuid.UUID,
    data: ProjectAccessGrantCreate,
    current_user: User = Depends(require_permission(Permission.ACCESS_MANAGE)),
    service: AccessGrantService = Depends(get_access_grant_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ProjectAccessGrantRead:
    grant = service.grant_project_access(project_id, data.user_id, granted_by=current_user)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ACCESS_GRANT_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project",
        resource_id=str(project_id),
        request_id=request_id_var.get(),
        metadata={"target_user_id": str(data.user_id)},
    )
    return ProjectAccessGrantRead.model_validate(grant)


@router.delete(
    "/api/v1/projects/{project_id}/access-grants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def revoke_project_access(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.ACCESS_MANAGE)),
    service: AccessGrantService = Depends(get_access_grant_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.revoke_project_access(project_id, user_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ACCESS_GRANT_REVOKE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="project",
        resource_id=str(project_id),
        request_id=request_id_var.get(),
        metadata={"target_user_id": str(user_id)},
    )

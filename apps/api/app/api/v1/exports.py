import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_audit_service, get_current_membership, require_permission
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.domain.import_export_parsing import ExportFormat, ImportEntityType
from app.models.enums import AuditAction, AuditOutcome
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.prioritization_framework import PrioritizationFrameworkRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_dependency import ProjectDependencyRepository
from app.repositories.project_priority_score import ProjectPriorityScoreRepository
from app.repositories.project_skill_requirement import ProjectSkillRequirementRepository
from app.repositories.risk import RiskRepository
from app.repositories.skill import SkillRepository
from app.repositories.stakeholder import StakeholderRepository
from app.repositories.team import TeamRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.services.audit import AuditService
from app.services.export_service import ExportService

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


def get_export_service(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> ExportService:
    return ExportService(
        PersonRepository(db),
        TeamRepository(db),
        TeamMembershipRepository(db),
        ProjectRepository(db),
        AllocationRepository(db),
        WorkingScheduleRepository(db),
        AvailabilityExceptionRepository(db),
        SkillRepository(db),
        PersonSkillRepository(db),
        ProjectSkillRequirementRepository(db),
        RiskRepository(db),
        StakeholderRepository(db),
        PrioritizationFrameworkRepository(db),
        ProjectPriorityScoreRepository(db),
        ProjectDependencyRepository(db),
        max_rows=settings.export_max_rows,
    )


@router.get("/{entity_type}")
def export_entities(
    entity_type: ImportEntityType,
    format: ExportFormat = Query(...),
    person_id: uuid.UUID | None = Query(default=None),
    team_id: uuid.UUID | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(require_permission(Permission.EXPORT_USE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ExportService = Depends(get_export_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> Response:
    """Exports source facts only — never a derived capacity/utilization
    value (CLAUDE.md §39 Phase 6). Scope filters reuse the same repository
    methods every other read endpoint already uses; an unscoped export is
    capped at Settings.export_max_rows, rejected with 422 rather than
    silently truncated if exceeded. Organization-scoped (Phase 12) — see
    ExportService's docstring."""
    content, filename, media_type = service.export(
        membership.organization_id,
        entity_type,
        format,
        person_id=person_id,
        team_id=team_id,
        project_id=project_id,
    )
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.EXPORT_USE,
        outcome=AuditOutcome.SUCCESS,
        resource_type=entity_type.value,
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"format": format.value},
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

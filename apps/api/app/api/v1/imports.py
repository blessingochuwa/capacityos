import logging

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_audit_service, get_current_membership, require_csrf, require_permission
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.domain.import_export_parsing import (
    ExportFormat,
    ImportEntityType,
    ImportMode,
    build_template,
)
from app.models.enums import AuditAction, AuditOutcome
from app.models.organization_membership import OrganizationMembership
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
from app.schemas.import_export import ImportApplyResult, ImportValidationReport
from app.services.allocation import AllocationService
from app.services.audit import AuditService
from app.services.availability_exception import AvailabilityExceptionService
from app.services.import_service import ImportService
from app.services.person import PersonService
from app.services.person_skill import PersonSkillService
from app.services.project import ProjectService
from app.services.project_skill_requirement import ProjectSkillRequirementService
from app.services.skill import SkillService
from app.services.team import TeamService
from app.services.team_membership import TeamMembershipService
from app.services.working_schedule import WorkingScheduleService

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])
logger = logging.getLogger("capacityos.imports")


def get_import_service(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> ImportService:
    return ImportService(
        PersonRepository(db),
        PersonService(PersonRepository(db)),
        TeamRepository(db),
        TeamService(TeamRepository(db)),
        TeamMembershipRepository(db),
        TeamMembershipService(
            TeamMembershipRepository(db), PersonRepository(db), TeamRepository(db)
        ),
        ProjectRepository(db),
        ProjectService(ProjectRepository(db)),
        AllocationRepository(db),
        AllocationService(AllocationRepository(db), PersonRepository(db), ProjectRepository(db)),
        WorkingScheduleRepository(db),
        WorkingScheduleService(WorkingScheduleRepository(db), PersonRepository(db)),
        AvailabilityExceptionRepository(db),
        AvailabilityExceptionService(AvailabilityExceptionRepository(db), PersonRepository(db)),
        SkillRepository(db),
        SkillService(SkillRepository(db)),
        PersonSkillRepository(db),
        PersonSkillService(PersonSkillRepository(db), PersonRepository(db), SkillRepository(db)),
        ProjectSkillRequirementRepository(db),
        ProjectSkillRequirementService(
            ProjectSkillRequirementRepository(db), ProjectRepository(db), SkillRepository(db)
        ),
        max_file_size_bytes=settings.import_max_file_size_bytes,
        max_rows=settings.import_max_rows,
    )


@router.get("/{entity_type}/template")
def get_import_template(
    entity_type: ImportEntityType,
    format: ExportFormat = Query(default=ExportFormat.CSV),
    _: User = Depends(require_permission(Permission.IMPORT_USE)),
) -> Response:
    """A downloadable example file for this entity type — the real headers
    plus one realistic, schema-valid row (CLAUDE.md §39 Phase 6 spec Step
    13). Pure and DB-free, unlike validate/apply, so it needs no
    ImportService."""
    content = build_template(entity_type, format)
    media_type = "text/csv" if format == ExportFormat.CSV else "application/json"
    filename = f"{entity_type.value}_template.{format.value}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{entity_type}/validate", response_model=ImportValidationReport)
def validate_import(
    entity_type: ImportEntityType,
    file: UploadFile = File(...),
    mode: ImportMode = Query(default=ImportMode.UPSERT),
    _: User = Depends(require_permission(Permission.IMPORT_USE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ImportService = Depends(get_import_service),
) -> ImportValidationReport:
    """Parses and validates the uploaded file without writing anything —
    stage A of the two-stage validate-then-apply flow (CLAUDE.md §39
    Phase 6). Never mutates live data."""
    raw_bytes = file.file.read()
    report = service.validate(
        membership.organization_id, entity_type, raw_bytes, file.filename, file.content_type, mode
    )
    # File name and row counts only — never the file's content.
    if report.file_error is not None or report.invalid_count > 0:
        logger.info(
            "import validation found errors",
            extra={
                "entity_type": entity_type.value,
                "mode": mode.value,
                "upload_filename": file.filename,
                "file_error": report.file_error,
                "invalid_count": report.invalid_count,
                "total_rows": report.total_rows,
            },
        )
    return report


@router.post(
    "/{entity_type}/apply", response_model=ImportApplyResult, dependencies=[Depends(require_csrf)]
)
def apply_import(
    entity_type: ImportEntityType,
    file: UploadFile = File(...),
    mode: ImportMode = Query(default=ImportMode.UPSERT),
    current_user: User = Depends(require_permission(Permission.IMPORT_USE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ImportService = Depends(get_import_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ImportApplyResult:
    """Re-validates the SAME file and, only if every row is clean, applies
    it atomically — stage B. The client is responsible for re-uploading the
    identical file it already validated (see
    docs/adr/0006-phase-6-import-export.md)."""
    raw_bytes = file.file.read()
    result = service.apply(
        membership.organization_id, entity_type, raw_bytes, file.filename, file.content_type, mode
    )
    log_level = logging.INFO if result.applied else logging.WARNING
    logger.log(
        log_level,
        "import apply completed",
        extra={
            "entity_type": entity_type.value,
            "mode": mode.value,
            "upload_filename": file.filename,
            "applied": result.applied,
            "created_count": result.created_count,
            "updated_count": result.updated_count,
            "invalid_count": result.invalid_count,
        },
    )
    # Never the file content — entity type, mode, and result counts only
    # (see docs/adr/0010-authentication-rbac-audit.md).
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.IMPORT_APPLY,
        outcome=AuditOutcome.SUCCESS if result.applied else AuditOutcome.FAILURE,
        resource_type=entity_type.value,
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={
            "mode": mode.value,
            "applied": result.applied,
            "created_count": result.created_count,
            "updated_count": result.updated_count,
            "invalid_count": result.invalid_count,
        },
    )
    return result

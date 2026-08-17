import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domain.import_export_parsing import ExportFormat, ImportEntityType
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
        max_rows=settings.export_max_rows,
    )


@router.get("/{entity_type}")
def export_entities(
    entity_type: ImportEntityType,
    format: ExportFormat = Query(...),
    person_id: uuid.UUID | None = Query(default=None),
    team_id: uuid.UUID | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    service: ExportService = Depends(get_export_service),
) -> Response:
    """Exports source facts only — never a derived capacity/utilization
    value (CLAUDE.md §39 Phase 6). Scope filters reuse the same repository
    methods every other read endpoint already uses; an unscoped export is
    capped at Settings.export_max_rows, rejected with 422 rather than
    silently truncated if exceeded."""
    content, filename, media_type = service.export(
        entity_type, format, person_id=person_id, team_id=team_id, project_id=project_id
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

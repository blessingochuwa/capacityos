import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, require_permission
from app.api.v1.scenarios import get_scenario_calculation_service
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domain.authorization import Permission
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
from app.schemas.common import Page
from app.schemas.insights import InsightsSummaryRead, SignalRead
from app.services.capacity import CapacityService
from app.services.insight_service import InsightService

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


def get_insight_service(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> InsightService:
    capacity_service = CapacityService(
        WorkingScheduleRepository(db),
        AvailabilityExceptionRepository(db),
        AllocationRepository(db),
        PersonRepository(db),
        TeamRepository(db),
        TeamMembershipRepository(db),
        ProjectRepository(db),
    )
    return InsightService(
        WorkingScheduleRepository(db),
        AvailabilityExceptionRepository(db),
        AllocationRepository(db),
        PersonRepository(db),
        TeamRepository(db),
        ProjectRepository(db),
        capacity_service,
        get_scenario_calculation_service(db),
        low_capacity_threshold_hours_per_day=settings.low_capacity_threshold_hours_per_day,
        person_skill_repository=PersonSkillRepository(db),
        skill_repository=SkillRepository(db),
        project_skill_requirement_repository=ProjectSkillRequirementRepository(db),
    )


@router.get("/people/{person_id}/signals", response_model=Page[SignalRead])
def get_person_signals(
    person_id: uuid.UUID,
    start_date: date,
    end_date: date,
    _: User = Depends(require_permission(Permission.INSIGHT_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: InsightService = Depends(get_insight_service),
) -> Page[SignalRead]:
    items = service.get_person_signals(
        membership.organization_id, person_id, start_date, end_date
    )
    return Page[SignalRead](items=items, total=len(items))


@router.get("/teams/{team_id}/signals", response_model=Page[SignalRead])
def get_team_signals(
    team_id: uuid.UUID,
    start_date: date,
    end_date: date,
    _: User = Depends(require_permission(Permission.INSIGHT_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: InsightService = Depends(get_insight_service),
) -> Page[SignalRead]:
    items = service.get_team_signals(membership.organization_id, team_id, start_date, end_date)
    return Page[SignalRead](items=items, total=len(items))


@router.get("/projects/{project_id}/signals", response_model=Page[SignalRead])
def get_project_signals(
    project_id: uuid.UUID,
    start_date: date,
    end_date: date,
    _: User = Depends(require_permission(Permission.INSIGHT_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: InsightService = Depends(get_insight_service),
) -> Page[SignalRead]:
    items = service.get_project_signals(
        membership.organization_id, project_id, start_date, end_date
    )
    return Page[SignalRead](items=items, total=len(items))


@router.get("/scenarios/{scenario_id}/signals", response_model=Page[SignalRead])
def get_scenario_signals(
    scenario_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.INSIGHT_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: InsightService = Depends(get_insight_service),
) -> Page[SignalRead]:
    items = service.get_scenario_signals(membership.organization_id, scenario_id)
    return Page[SignalRead](items=items, total=len(items))


@router.get("/teams/{team_id}/summary", response_model=InsightsSummaryRead)
def get_team_summary(
    team_id: uuid.UUID,
    start_date: date,
    end_date: date,
    project_id: uuid.UUID | None = Query(default=None),
    scenario_id: uuid.UUID | None = Query(default=None),
    _: User = Depends(require_permission(Permission.INSIGHT_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: InsightService = Depends(get_insight_service),
) -> InsightsSummaryRead:
    return service.get_team_summary(
        membership.organization_id, team_id, start_date, end_date, project_id, scenario_id
    )

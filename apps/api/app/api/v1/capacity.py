import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.domain.authorization import Permission
from app.domain.capacity import DailyCapacity, PersonCapacityResult
from app.models.user import User
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.team import TeamRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.capacity import (
    DailyCapacityRead,
    PersonCapacityRead,
    ProjectDailyDemandRead,
    ProjectDemandRead,
    ProjectPersonDemandRead,
    TeamCapacityRead,
)
from app.services.capacity import CapacityService

router = APIRouter(prefix="/api/v1/capacity", tags=["capacity"])


def get_capacity_service(db: Session = Depends(get_db)) -> CapacityService:
    return CapacityService(
        WorkingScheduleRepository(db),
        AvailabilityExceptionRepository(db),
        AllocationRepository(db),
        PersonRepository(db),
        TeamRepository(db),
        TeamMembershipRepository(db),
        ProjectRepository(db),
    )


def _daily_to_read(day: DailyCapacity) -> DailyCapacityRead:
    return DailyCapacityRead(
        date=day.date,
        scheduled_hours=day.scheduled_hours,
        unavailable_hours=day.unavailable_hours,
        effective_capacity=day.effective_capacity,
        allocated_hours=day.allocated_hours,
        remaining_capacity=day.remaining_capacity,
        utilization=day.utilization,
        over_allocation=day.over_allocation,
    )


def _person_result_to_read(
    person_id: uuid.UUID, result: PersonCapacityResult
) -> PersonCapacityRead:
    return PersonCapacityRead(
        person_id=person_id,
        start_date=result.start_date,
        end_date=result.end_date,
        gross_capacity=result.gross_capacity,
        unavailable_hours=result.unavailable_hours,
        effective_capacity=result.effective_capacity,
        allocated_hours=result.allocated_hours,
        remaining_capacity=result.remaining_capacity,
        utilization=result.utilization,
        over_allocation=result.over_allocation,
        daily_breakdown=[_daily_to_read(day) for day in result.daily_breakdown],
    )


@router.get("/people/{person_id}", response_model=PersonCapacityRead)
def get_person_capacity(
    person_id: uuid.UUID,
    start_date: date,
    end_date: date,
    _: User = Depends(require_permission(Permission.PERSON_READ)),
    service: CapacityService = Depends(get_capacity_service),
) -> PersonCapacityRead:
    result = service.get_person_capacity(person_id, start_date, end_date)
    return _person_result_to_read(person_id, result)


@router.get("/teams/{team_id}", response_model=TeamCapacityRead)
def get_team_capacity(
    team_id: uuid.UUID,
    start_date: date,
    end_date: date,
    _: User = Depends(require_permission(Permission.TEAM_READ)),
    service: CapacityService = Depends(get_capacity_service),
) -> TeamCapacityRead:
    team_result, members = service.get_team_capacity(team_id, start_date, end_date)
    return TeamCapacityRead(
        team_id=team_id,
        start_date=team_result.start_date,
        end_date=team_result.end_date,
        gross_capacity=team_result.gross_capacity,
        unavailable_hours=team_result.unavailable_hours,
        effective_capacity=team_result.effective_capacity,
        allocated_hours=team_result.allocated_hours,
        remaining_capacity=team_result.remaining_capacity,
        utilization=team_result.utilization,
        over_allocation=team_result.over_allocation,
        members=[_person_result_to_read(person_id, result) for person_id, result in members],
    )


@router.get("/projects/{project_id}", response_model=ProjectDemandRead)
def get_project_demand(
    project_id: uuid.UUID,
    start_date: date,
    end_date: date,
    _: User = Depends(require_permission(Permission.PROJECT_READ)),
    service: CapacityService = Depends(get_capacity_service),
) -> ProjectDemandRead:
    result = service.get_project_demand(project_id, start_date, end_date)
    return ProjectDemandRead(
        project_id=project_id,
        start_date=result.start_date,
        end_date=result.end_date,
        allocated_hours=result.allocated_hours,
        allocated_people=result.allocated_people,
        daily_breakdown=[
            ProjectDailyDemandRead(date=day.date, allocated_hours=day.allocated_hours)
            for day in result.daily_breakdown
        ],
        by_person=[
            ProjectPersonDemandRead(
                person_id=entry.person_id, allocated_hours=entry.allocated_hours
            )
            for entry in result.by_person
        ],
    )

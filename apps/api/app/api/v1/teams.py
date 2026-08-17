import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
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


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(data: TeamCreate, service: TeamService = Depends(get_team_service)) -> TeamRead:
    return TeamRead.model_validate(service.create(data))


@router.get("", response_model=Page[TeamRead])
def list_teams(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: TeamService = Depends(get_team_service),
) -> Page[TeamRead]:
    items, total = service.list(limit=limit, offset=offset)
    return Page[TeamRead](items=[TeamRead.model_validate(item) for item in items], total=total)


@router.get("/{team_id}", response_model=TeamRead)
def get_team(team_id: uuid.UUID, service: TeamService = Depends(get_team_service)) -> TeamRead:
    return TeamRead.model_validate(service.get(team_id))


@router.patch("/{team_id}", response_model=TeamRead)
def update_team(
    team_id: uuid.UUID, data: TeamUpdate, service: TeamService = Depends(get_team_service)
) -> TeamRead:
    return TeamRead.model_validate(service.update(team_id, data))


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(team_id: uuid.UUID, service: TeamService = Depends(get_team_service)) -> None:
    service.delete(team_id)


@router.get("/{team_id}/members", response_model=list[TeamMembershipRead])
def list_team_members(
    team_id: uuid.UUID, service: TeamMembershipService = Depends(get_team_membership_service)
) -> list[TeamMembershipRead]:
    return [TeamMembershipRead.model_validate(m) for m in service.list_members(team_id)]


@router.post(
    "/{team_id}/members", response_model=TeamMembershipRead, status_code=status.HTTP_201_CREATED
)
def add_team_member(
    team_id: uuid.UUID,
    data: TeamMembershipCreate,
    service: TeamMembershipService = Depends(get_team_membership_service),
) -> TeamMembershipRead:
    return TeamMembershipRead.model_validate(service.add_member(team_id, data))


@router.delete("/{team_id}/members/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(
    team_id: uuid.UUID,
    person_id: uuid.UUID,
    service: TeamMembershipService = Depends(get_team_membership_service),
) -> None:
    service.remove_member(team_id, person_id)


@router.get("/{team_id}/skill-capacity", response_model=TeamSkillCapacityRead)
def get_team_skill_capacity(
    team_id: uuid.UUID,
    start_date: date,
    end_date: date,
    service: SkillCapacityService = Depends(get_skill_capacity_service),
) -> TeamSkillCapacityRead:
    return service.get_team_skill_capacity(team_id, start_date, end_date)

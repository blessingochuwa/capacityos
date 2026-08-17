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
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.project_skill_requirement import (
    ProjectSkillRequirementCreate,
    ProjectSkillRequirementRead,
    ProjectSkillRequirementUpdate,
)
from app.schemas.skill_capacity import ProjectSkillCoverageRead
from app.services.project import ProjectService
from app.services.project_skill_requirement import ProjectSkillRequirementService
from app.services.skill_capacity import SkillCapacityService

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(ProjectRepository(db))


def get_project_skill_requirement_service(
    db: Session = Depends(get_db),
) -> ProjectSkillRequirementService:
    return ProjectSkillRequirementService(
        ProjectSkillRequirementRepository(db), ProjectRepository(db), SkillRepository(db)
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


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate, service: ProjectService = Depends(get_project_service)
) -> ProjectRead:
    return ProjectRead.model_validate(service.create(data))


@router.get("", response_model=Page[ProjectRead])
def list_projects(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ProjectService = Depends(get_project_service),
) -> Page[ProjectRead]:
    items, total = service.list(limit=limit, offset=offset)
    return Page[ProjectRead](
        items=[ProjectRead.model_validate(item) for item in items], total=total
    )


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: uuid.UUID, service: ProjectService = Depends(get_project_service)
) -> ProjectRead:
    return ProjectRead.model_validate(service.get(project_id))


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    return ProjectRead.model_validate(service.update(project_id, data))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID, service: ProjectService = Depends(get_project_service)
) -> None:
    service.delete(project_id)


@router.get(
    "/{project_id}/skill-requirements", response_model=list[ProjectSkillRequirementRead]
)
def list_project_skill_requirements(
    project_id: uuid.UUID,
    service: ProjectSkillRequirementService = Depends(get_project_skill_requirement_service),
) -> list[ProjectSkillRequirementRead]:
    return [
        ProjectSkillRequirementRead.model_validate(row)
        for row in service.list_for_project(project_id)
    ]


@router.post(
    "/{project_id}/skill-requirements",
    response_model=ProjectSkillRequirementRead,
    status_code=status.HTTP_201_CREATED,
)
def add_project_skill_requirement(
    project_id: uuid.UUID,
    data: ProjectSkillRequirementCreate,
    service: ProjectSkillRequirementService = Depends(get_project_skill_requirement_service),
) -> ProjectSkillRequirementRead:
    return ProjectSkillRequirementRead.model_validate(service.add(project_id, data))


@router.patch(
    "/{project_id}/skill-requirements/{requirement_id}",
    response_model=ProjectSkillRequirementRead,
)
def update_project_skill_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    data: ProjectSkillRequirementUpdate,
    service: ProjectSkillRequirementService = Depends(get_project_skill_requirement_service),
) -> ProjectSkillRequirementRead:
    return ProjectSkillRequirementRead.model_validate(
        service.update(project_id, requirement_id, data)
    )


@router.delete(
    "/{project_id}/skill-requirements/{requirement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_project_skill_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    service: ProjectSkillRequirementService = Depends(get_project_skill_requirement_service),
) -> None:
    service.remove(project_id, requirement_id)


@router.get("/{project_id}/skill-coverage", response_model=ProjectSkillCoverageRead)
def get_project_skill_coverage(
    project_id: uuid.UUID,
    start_date: date,
    end_date: date,
    service: SkillCapacityService = Depends(get_skill_capacity_service),
) -> ProjectSkillCoverageRead:
    return service.get_project_skill_coverage(project_id, start_date, end_date)

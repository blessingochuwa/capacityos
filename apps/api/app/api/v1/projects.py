import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.project import ProjectRepository
from app.schemas.common import Page
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(ProjectRepository(db))


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

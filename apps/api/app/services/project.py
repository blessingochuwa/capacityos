import uuid

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.models.project import Project
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    def create(self, data: ProjectCreate) -> Project:
        if data.external_id is not None and self.repository.get_by_external_id(
            data.external_id
        ):
            raise ConflictError(f"A project with external_id {data.external_id} already exists.")

        project = Project(
            name=data.name,
            description=data.description,
            status=data.status,
            start_date=data.start_date,
            end_date=data.end_date,
            external_id=data.external_id,
        )
        return self.repository.add(project)

    def get(self, project_id: uuid.UUID) -> Project:
        project = self.repository.get(project_id)
        if project is None:
            raise NotFoundError("Project", project_id)
        return project

    def list(self, *, limit: int = 100, offset: int = 0) -> tuple[list[Project], int]:
        return self.repository.list(limit=limit, offset=offset)

    def update(self, project_id: uuid.UUID, data: ProjectUpdate) -> Project:
        project = self.get(project_id)
        updates = data.model_dump(exclude_unset=True)

        merged_start = updates.get("start_date", project.start_date)
        merged_end = updates.get("end_date", project.end_date)
        if merged_start and merged_end and merged_end < merged_start:
            raise DomainValidationError("end_date cannot precede start_date")

        new_external_id = updates.get("external_id")
        if new_external_id is not None and new_external_id != project.external_id:
            existing = self.repository.get_by_external_id(new_external_id)
            if existing is not None and existing.id != project.id:
                raise ConflictError(
                    f"A project with external_id {new_external_id} already exists."
                )

        for field, value in updates.items():
            setattr(project, field, value)
        self.repository.session.flush()
        return project

    def delete(self, project_id: uuid.UUID) -> None:
        self.repository.delete(self.get(project_id))

import uuid

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.domain.prioritization import detects_cycle
from app.models.enums import ProjectDependencyType
from app.models.project_dependency import ProjectDependency
from app.repositories.project import ProjectRepository
from app.repositories.project_dependency import ProjectDependencyRepository
from app.schemas.prioritization import ProjectDependencyCreate


class ProjectDependencyService:
    """Organization-scoped (Phase 12), project-nested — a dependency edge
    is created/deleted through its `from_project`'s URL, matching
    ProjectDependencyCreate's "the URL names the owning project"
    convention (see its docstring). Both projects are independently
    verified same-organization before an edge is ever written, the same
    discipline as ProjectPriorityScoreService's project_id/framework_id
    checks."""

    def __init__(
        self, repository: ProjectDependencyRepository, project_repository: ProjectRepository
    ) -> None:
        self.repository = repository
        self.project_repository = project_repository

    def create(
        self, organization_id: uuid.UUID, from_project_id: uuid.UUID, data: ProjectDependencyCreate
    ) -> ProjectDependency:
        if self.project_repository.get(from_project_id, organization_id) is None:
            raise NotFoundError("Project", from_project_id)
        if self.project_repository.get(data.to_project_id, organization_id) is None:
            raise NotFoundError("Project", data.to_project_id)
        if from_project_id == data.to_project_id:
            raise DomainValidationError("A project cannot depend on itself.")
        if (
            self.repository.get_by_natural_key(
                from_project_id, data.to_project_id, data.dependency_type, organization_id
            )
            is not None
        ):
            raise ConflictError(
                "This dependency edge already exists between these two projects."
            )

        if data.dependency_type == ProjectDependencyType.BLOCKS:
            existing_edges = self.repository.list_blocks_edges(organization_id)
            edges_as_strings = [(str(a), str(b)) for a, b in existing_edges]
            if detects_cycle(
                edges_as_strings, (str(from_project_id), str(data.to_project_id))
            ):
                raise DomainValidationError(
                    "This dependency would create a cycle in the project dependency graph."
                )

        dependency = self.repository.add(
            ProjectDependency(
                organization_id=organization_id,
                from_project_id=from_project_id,
                to_project_id=data.to_project_id,
                dependency_type=data.dependency_type,
            )
        )
        self.repository.session.flush()
        self.repository.session.refresh(dependency, attribute_names=["from_project", "to_project"])
        return dependency

    def list_for_project(
        self, organization_id: uuid.UUID, project_id: uuid.UUID
    ) -> list[ProjectDependency]:
        if self.project_repository.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)
        return self.repository.list_for_project(project_id, organization_id)

    def delete(
        self, organization_id: uuid.UUID, from_project_id: uuid.UUID, dependency_id: uuid.UUID
    ) -> None:
        dependency = self.repository.get(dependency_id, organization_id)
        if dependency is None or dependency.from_project_id != from_project_id:
            raise NotFoundError("ProjectDependency", dependency_id)
        self.repository.delete(dependency)

    def graph(self, organization_id: uuid.UUID) -> list[ProjectDependency]:
        return self.repository.list_for_organization(organization_id)

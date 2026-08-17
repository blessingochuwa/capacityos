import uuid

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.models.project_skill_requirement import ProjectSkillRequirement
from app.repositories.project import ProjectRepository
from app.repositories.project_skill_requirement import ProjectSkillRequirementRepository
from app.repositories.skill import SkillRepository
from app.schemas.project_skill_requirement import (
    ProjectSkillRequirementCreate,
    ProjectSkillRequirementUpdate,
)


class ProjectSkillRequirementService:
    def __init__(
        self,
        repository: ProjectSkillRequirementRepository,
        project_repository: ProjectRepository,
        skill_repository: SkillRepository,
    ) -> None:
        self.repository = repository
        self.project_repository = project_repository
        self.skill_repository = skill_repository

    def add(
        self, project_id: uuid.UUID, data: ProjectSkillRequirementCreate
    ) -> ProjectSkillRequirement:
        if self.project_repository.get(project_id) is None:
            raise NotFoundError("Project", project_id)
        skill = self.skill_repository.get(data.skill_id)
        if skill is None:
            raise NotFoundError("Skill", data.skill_id)
        if not skill.is_active:
            raise DomainValidationError(f"Skill '{skill.name}' is not active.")
        if self.repository.get_by_project_and_skill(project_id, data.skill_id) is not None:
            raise ConflictError("This project already has a requirement for this skill.")

        requirement = ProjectSkillRequirement(
            project_id=project_id,
            skill_id=data.skill_id,
            required_hours=data.required_hours,
            minimum_proficiency=data.minimum_proficiency,
            notes=data.notes,
        )
        return self.repository.add(requirement)

    def list_for_project(self, project_id: uuid.UUID) -> list[ProjectSkillRequirement]:
        if self.project_repository.get(project_id) is None:
            raise NotFoundError("Project", project_id)
        return self.repository.list_for_project(project_id)

    def update(
        self,
        project_id: uuid.UUID,
        requirement_id: uuid.UUID,
        data: ProjectSkillRequirementUpdate,
    ) -> ProjectSkillRequirement:
        requirement = self._get_owned(project_id, requirement_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(requirement, field, value)
        self.repository.session.flush()
        return requirement

    def remove(self, project_id: uuid.UUID, requirement_id: uuid.UUID) -> None:
        requirement = self._get_owned(project_id, requirement_id)
        self.repository.delete(requirement)

    def _get_owned(
        self, project_id: uuid.UUID, requirement_id: uuid.UUID
    ) -> ProjectSkillRequirement:
        requirement = self.repository.get(requirement_id)
        if requirement is None or requirement.project_id != project_id:
            raise NotFoundError("ProjectSkillRequirement", requirement_id)
        return requirement

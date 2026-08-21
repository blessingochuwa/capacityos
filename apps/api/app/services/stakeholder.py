import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.stakeholder import Stakeholder
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.stakeholder import StakeholderRepository
from app.schemas.stakeholder import StakeholderCreate, StakeholderUpdate


class StakeholderService:
    """Organization-scoped (Phase 12) — project_id/person_id are verified
    same-organization by construction, same reasoning as
    PersonSkillService/RiskService (see their docstrings)."""

    def __init__(
        self,
        repository: StakeholderRepository,
        project_repository: ProjectRepository,
        person_repository: PersonRepository,
    ) -> None:
        self.repository = repository
        self.project_repository = project_repository
        self.person_repository = person_repository

    def create(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, data: StakeholderCreate
    ) -> Stakeholder:
        if self.project_repository.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)
        if data.person_id is not None:
            self._require_person(organization_id, data.person_id)
            if (
                self.repository.get_by_project_and_person(
                    project_id, data.person_id, organization_id
                )
                is not None
            ):
                raise ConflictError(
                    "This person is already recorded as a stakeholder on this project."
                )

        stakeholder = Stakeholder(
            organization_id=organization_id,
            project_id=project_id,
            name=data.name,
            person_id=data.person_id,
            role=data.role,
            influence=data.influence,
            interest=data.interest,
            decision_authority=data.decision_authority,
            communication_needs=data.communication_needs,
        )
        return self.repository.add(stakeholder)

    def list_for_project(
        self, organization_id: uuid.UUID, project_id: uuid.UUID
    ) -> list[Stakeholder]:
        if self.project_repository.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)
        return self.repository.list_for_project(project_id, organization_id)

    def update(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        stakeholder_id: uuid.UUID,
        data: StakeholderUpdate,
    ) -> Stakeholder:
        stakeholder = self._get_owned(organization_id, project_id, stakeholder_id)
        updates = data.model_dump(exclude_unset=True)

        new_person_id = updates.get("person_id")
        if new_person_id is not None and new_person_id != stakeholder.person_id:
            self._require_person(organization_id, new_person_id)
            existing = self.repository.get_by_project_and_person(
                project_id, new_person_id, organization_id
            )
            if existing is not None and existing.id != stakeholder.id:
                raise ConflictError(
                    "This person is already recorded as a stakeholder on this project."
                )

        for field, value in updates.items():
            setattr(stakeholder, field, value)
        self.repository.session.flush()
        return stakeholder

    def delete(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, stakeholder_id: uuid.UUID
    ) -> None:
        stakeholder = self._get_owned(organization_id, project_id, stakeholder_id)
        self.repository.delete(stakeholder)

    def _require_person(self, organization_id: uuid.UUID, person_id: uuid.UUID) -> None:
        if self.person_repository.get(person_id, organization_id) is None:
            raise NotFoundError("Person", person_id)

    def _get_owned(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, stakeholder_id: uuid.UUID
    ) -> Stakeholder:
        stakeholder = self.repository.get(stakeholder_id, organization_id)
        if stakeholder is None or stakeholder.project_id != project_id:
            raise NotFoundError("Stakeholder", stakeholder_id)
        return stakeholder

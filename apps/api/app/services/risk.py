import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.risk import Risk
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.risk import RiskRepository
from app.schemas.risk import RiskCreate, RiskUpdate


class RiskService:
    """Organization-scoped (Phase 12) — project_id/owner_person_id are
    verified same-organization by construction, same reasoning as
    PersonSkillService/ProjectSkillRequirementService (see their
    docstrings)."""

    def __init__(
        self,
        repository: RiskRepository,
        project_repository: ProjectRepository,
        person_repository: PersonRepository,
    ) -> None:
        self.repository = repository
        self.project_repository = project_repository
        self.person_repository = person_repository

    def create(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, data: RiskCreate
    ) -> Risk:
        if self.project_repository.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)
        if data.owner_person_id is not None:
            self._require_owner(organization_id, data.owner_person_id)
        if data.external_id is not None and self.repository.get_by_external_id(
            data.external_id, organization_id
        ):
            raise ConflictError(f"A risk with external_id {data.external_id} already exists.")

        risk = Risk(
            organization_id=organization_id,
            project_id=project_id,
            description=data.description,
            cause=data.cause,
            potential_effect=data.potential_effect,
            probability=data.probability,
            impact=data.impact,
            response=data.response,
            owner_person_id=data.owner_person_id,
            status=data.status,
            review_date=data.review_date,
            external_id=data.external_id,
        )
        return self.repository.add(risk)

    def list_for_project(self, organization_id: uuid.UUID, project_id: uuid.UUID) -> list[Risk]:
        if self.project_repository.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)
        return self.repository.list_for_project(project_id, organization_id)

    def update(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        risk_id: uuid.UUID,
        data: RiskUpdate,
    ) -> Risk:
        risk = self._get_owned(organization_id, project_id, risk_id)
        updates = data.model_dump(exclude_unset=True)

        new_owner_id = updates.get("owner_person_id")
        if new_owner_id is not None:
            self._require_owner(organization_id, new_owner_id)

        new_external_id = updates.get("external_id")
        if new_external_id is not None and new_external_id != risk.external_id:
            existing = self.repository.get_by_external_id(new_external_id, organization_id)
            if existing is not None and existing.id != risk.id:
                raise ConflictError(f"A risk with external_id {new_external_id} already exists.")

        for field, value in updates.items():
            setattr(risk, field, value)
        self.repository.session.flush()
        return risk

    def delete(self, organization_id: uuid.UUID, project_id: uuid.UUID, risk_id: uuid.UUID) -> None:
        risk = self._get_owned(organization_id, project_id, risk_id)
        self.repository.delete(risk)

    def _require_owner(self, organization_id: uuid.UUID, owner_person_id: uuid.UUID) -> None:
        if self.person_repository.get(owner_person_id, organization_id) is None:
            raise NotFoundError("Person", owner_person_id)

    def _get_owned(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, risk_id: uuid.UUID
    ) -> Risk:
        risk = self.repository.get(risk_id, organization_id)
        if risk is None or risk.project_id != project_id:
            raise NotFoundError("Risk", risk_id)
        return risk

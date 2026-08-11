import uuid

from app.core.exceptions import DomainValidationError, NotFoundError
from app.models.allocation import Allocation
from app.repositories.allocation import AllocationRepository
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.schemas.allocation import AllocationCreate, AllocationUpdate


class AllocationService:
    def __init__(
        self,
        repository: AllocationRepository,
        person_repository: PersonRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self.repository = repository
        self.person_repository = person_repository
        self.project_repository = project_repository

    def create(self, data: AllocationCreate) -> Allocation:
        if self.person_repository.get(data.person_id) is None:
            raise NotFoundError("Person", data.person_id)
        if self.project_repository.get(data.project_id) is None:
            raise NotFoundError("Project", data.project_id)

        allocation = Allocation(
            person_id=data.person_id,
            project_id=data.project_id,
            start_date=data.start_date,
            end_date=data.end_date,
            allocation_hours=data.allocation_hours,
            allocation_unit=data.allocation_unit,
            notes=data.notes,
        )
        return self.repository.add(allocation)

    def get(self, allocation_id: uuid.UUID) -> Allocation:
        allocation = self.repository.get(allocation_id)
        if allocation is None:
            raise NotFoundError("Allocation", allocation_id)
        return allocation

    def list(
        self,
        *,
        person_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Allocation], int]:
        return self.repository.list_filtered(
            person_id=person_id, project_id=project_id, limit=limit, offset=offset
        )

    def update(self, allocation_id: uuid.UUID, data: AllocationUpdate) -> Allocation:
        allocation = self.get(allocation_id)
        updates = data.model_dump(exclude_unset=True)

        merged_start = updates.get("start_date", allocation.start_date)
        merged_end = updates.get("end_date", allocation.end_date)
        if merged_end < merged_start:
            raise DomainValidationError("end_date cannot precede start_date")

        for field, value in updates.items():
            setattr(allocation, field, value)
        self.repository.session.flush()
        return allocation

    def delete(self, allocation_id: uuid.UUID) -> None:
        self.repository.delete(self.get(allocation_id))

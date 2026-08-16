import uuid

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.models.availability_exception import AvailabilityException
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.schemas.availability_exception import (
    AvailabilityExceptionCreate,
    AvailabilityExceptionUpdate,
)


class AvailabilityExceptionService:
    def __init__(
        self,
        repository: AvailabilityExceptionRepository,
        person_repository: PersonRepository,
    ) -> None:
        self.repository = repository
        self.person_repository = person_repository

    def create(self, data: AvailabilityExceptionCreate) -> AvailabilityException:
        if self.person_repository.get(data.person_id) is None:
            raise NotFoundError("Person", data.person_id)
        if data.external_id is not None and self.repository.get_by_external_id(
            data.external_id
        ):
            raise ConflictError(
                f"An availability exception with external_id {data.external_id} already exists."
            )

        exception = AvailabilityException(
            person_id=data.person_id,
            start_date=data.start_date,
            end_date=data.end_date,
            availability_type=data.availability_type,
            hours=data.hours,
            notes=data.notes,
            external_id=data.external_id,
        )
        return self.repository.add(exception)

    def get(self, exception_id: uuid.UUID) -> AvailabilityException:
        exception = self.repository.get(exception_id)
        if exception is None:
            raise NotFoundError("AvailabilityException", exception_id)
        return exception

    def list(
        self, *, person_id: uuid.UUID | None = None, limit: int = 100, offset: int = 0
    ) -> tuple[list[AvailabilityException], int]:
        return self.repository.list_filtered(person_id=person_id, limit=limit, offset=offset)

    def update(
        self, exception_id: uuid.UUID, data: AvailabilityExceptionUpdate
    ) -> AvailabilityException:
        exception = self.get(exception_id)
        updates = data.model_dump(exclude_unset=True)

        merged_start = updates.get("start_date", exception.start_date)
        merged_end = updates.get("end_date", exception.end_date)
        if merged_end < merged_start:
            raise DomainValidationError("end_date cannot precede start_date")

        new_external_id = updates.get("external_id")
        if new_external_id is not None and new_external_id != exception.external_id:
            existing = self.repository.get_by_external_id(new_external_id)
            if existing is not None and existing.id != exception.id:
                raise ConflictError(
                    f"An availability exception with external_id {new_external_id} "
                    "already exists."
                )

        for field, value in updates.items():
            setattr(exception, field, value)
        self.repository.session.flush()
        return exception

    def delete(self, exception_id: uuid.UUID) -> None:
        self.repository.delete(self.get(exception_id))

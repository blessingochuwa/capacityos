import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.person import Person
from app.repositories.person import PersonRepository
from app.schemas.person import PersonCreate, PersonUpdate


class PersonService:
    """Organization-scoped (Phase 12) — every method takes organization_id
    as its first argument after self, resolved by the route from
    Depends(get_current_membership). A person_id belonging to a different
    organization is indistinguishable from a nonexistent one: repository
    lookups filtered on both id and organization_id return None, which
    the existing NotFoundError -> 404 path already handles with no new
    branching (see docs/adr/0012-organizations-multi-tenancy.md)."""

    def __init__(self, repository: PersonRepository) -> None:
        self.repository = repository

    def create(self, organization_id: uuid.UUID, data: PersonCreate) -> Person:
        if self.repository.get_by_email(data.email, organization_id) is not None:
            raise ConflictError(f"A person with email {data.email} already exists.")

        person = Person(
            organization_id=organization_id,
            first_name=data.first_name,
            last_name=data.last_name,
            display_name=data.display_name or f"{data.first_name} {data.last_name}",
            email=data.email,
            job_title=data.job_title,
            timezone=data.timezone,
            employment_status=data.employment_status,
        )
        return self.repository.add(person)

    def get(self, organization_id: uuid.UUID, person_id: uuid.UUID) -> Person:
        person = self.repository.get(person_id, organization_id)
        if person is None:
            raise NotFoundError("Person", person_id)
        return person

    def list(
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[Person], int]:
        return self.repository.list(organization_id, limit=limit, offset=offset)

    def update(
        self, organization_id: uuid.UUID, person_id: uuid.UUID, data: PersonUpdate
    ) -> Person:
        person = self.get(organization_id, person_id)
        updates = data.model_dump(exclude_unset=True)

        new_email = updates.get("email")
        if new_email is not None and new_email != person.email:
            existing = self.repository.get_by_email(new_email, organization_id)
            if existing is not None and existing.id != person.id:
                raise ConflictError(f"A person with email {new_email} already exists.")

        for field, value in updates.items():
            setattr(person, field, value)
        self.repository.session.flush()
        return person

    def delete(self, organization_id: uuid.UUID, person_id: uuid.UUID) -> None:
        self.repository.delete(self.get(organization_id, person_id))

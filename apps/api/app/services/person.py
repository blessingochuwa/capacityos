import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.person import Person
from app.repositories.person import PersonRepository
from app.schemas.person import PersonCreate, PersonUpdate


class PersonService:
    def __init__(self, repository: PersonRepository) -> None:
        self.repository = repository

    def create(self, data: PersonCreate) -> Person:
        if self.repository.get_by_email(data.email) is not None:
            raise ConflictError(f"A person with email {data.email} already exists.")

        person = Person(
            first_name=data.first_name,
            last_name=data.last_name,
            display_name=data.display_name or f"{data.first_name} {data.last_name}",
            email=data.email,
            job_title=data.job_title,
            timezone=data.timezone,
            employment_status=data.employment_status,
        )
        return self.repository.add(person)

    def get(self, person_id: uuid.UUID) -> Person:
        person = self.repository.get(person_id)
        if person is None:
            raise NotFoundError("Person", person_id)
        return person

    def list(self, *, limit: int = 100, offset: int = 0) -> tuple[list[Person], int]:
        return self.repository.list(limit=limit, offset=offset)

    def update(self, person_id: uuid.UUID, data: PersonUpdate) -> Person:
        person = self.get(person_id)
        updates = data.model_dump(exclude_unset=True)

        new_email = updates.get("email")
        if new_email is not None and new_email != person.email:
            existing = self.repository.get_by_email(new_email)
            if existing is not None and existing.id != person.id:
                raise ConflictError(f"A person with email {new_email} already exists.")

        for field, value in updates.items():
            setattr(person, field, value)
        self.repository.session.flush()
        return person

    def delete(self, person_id: uuid.UUID) -> None:
        self.repository.delete(self.get(person_id))

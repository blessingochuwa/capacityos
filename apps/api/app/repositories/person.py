import uuid

from sqlalchemy import select

from app.models.person import Person
from app.repositories.base import BaseRepository


class PersonRepository(BaseRepository[Person]):
    model = Person

    def get_by_email(self, email: str) -> Person | None:
        return self.session.scalar(select(Person).where(Person.email == email))

    def list_by_ids(self, person_ids: list[uuid.UUID]) -> list[Person]:
        """Batched lookup for a known set of ids — one query, not one per id
        (CLAUDE.md §27). Used by scenario calculation to label affected
        people (app/services/scenario_calculation.py)."""
        if not person_ids:
            return []
        return list(self.session.scalars(select(Person).where(Person.id.in_(person_ids))))

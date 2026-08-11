from sqlalchemy import select

from app.models.person import Person
from app.repositories.base import BaseRepository


class PersonRepository(BaseRepository[Person]):
    model = Person

    def get_by_email(self, email: str) -> Person | None:
        return self.session.scalar(select(Person).where(Person.email == email))

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import Base


class BaseRepository[ModelT: Base]:
    """Generic persistence operations shared by every entity repository.

    Holds no business rules or cross-entity checks — those belong in the
    service layer (see app/services/). Subclasses set `model` and add only
    the query methods their entity actually needs.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, id_: uuid.UUID) -> ModelT | None:
        return self.session.get(self.model, id_)

    def list(self, *, limit: int = 100, offset: int = 0) -> tuple[list[ModelT], int]:
        """Unordered pagination window. Entities that need a sensible sort
        (e.g. by date) define their own list method — see e.g.
        AllocationRepository.list_filtered."""
        total = self.session.scalar(select(func.count()).select_from(self.model)) or 0
        items = list(self.session.scalars(select(self.model).limit(limit).offset(offset)))
        return items, total

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        self.session.flush()
        return instance

    def delete(self, instance: ModelT) -> None:
        self.session.delete(instance)
        self.session.flush()

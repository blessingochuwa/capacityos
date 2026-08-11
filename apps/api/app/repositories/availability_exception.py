import uuid

from sqlalchemy import func, select

from app.models.availability_exception import AvailabilityException
from app.repositories.base import BaseRepository


class AvailabilityExceptionRepository(BaseRepository[AvailabilityException]):
    model = AvailabilityException

    def list_filtered(
        self, *, person_id: uuid.UUID | None = None, limit: int = 100, offset: int = 0
    ) -> tuple[list[AvailabilityException], int]:
        stmt = select(AvailabilityException)
        if person_id is not None:
            stmt = stmt.where(AvailabilityException.person_id == person_id)

        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.session.scalars(
                stmt.order_by(AvailabilityException.start_date).limit(limit).offset(offset)
            )
        )
        return items, total

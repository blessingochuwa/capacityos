import uuid
from datetime import date

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

    def list_for_people(
        self, person_ids: list[uuid.UUID], start_date: date, end_date: date
    ) -> list[AvailabilityException]:
        """Exceptions for any of person_ids overlapping [start_date, end_date],
        one query for the whole batch — see WorkingScheduleRepository.list_for_people."""
        if not person_ids:
            return []
        stmt = select(AvailabilityException).where(
            AvailabilityException.person_id.in_(person_ids),
            AvailabilityException.start_date <= end_date,
            AvailabilityException.end_date >= start_date,
        )
        return list(self.session.scalars(stmt))

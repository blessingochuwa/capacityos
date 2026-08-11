import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.working_schedule import WorkingSchedule
from app.repositories.base import BaseRepository


class WorkingScheduleRepository(BaseRepository[WorkingSchedule]):
    model = WorkingSchedule

    def list_for_person(self, person_id: uuid.UUID) -> list[WorkingSchedule]:
        return list(
            self.session.scalars(
                select(WorkingSchedule).where(WorkingSchedule.person_id == person_id)
            )
        )

    def list_for_people(
        self, person_ids: list[uuid.UUID], start_date: date, end_date: date
    ) -> list[WorkingSchedule]:
        """Schedules for any of person_ids whose effective range overlaps
        [start_date, end_date] — one query for the whole batch (used by the
        capacity engine for both single-person and team lookups) rather than
        one query per person, per CLAUDE.md §27. entries is eager-loaded
        since the capacity engine always needs it."""
        if not person_ids:
            return []
        stmt = (
            select(WorkingSchedule)
            .where(
                WorkingSchedule.person_id.in_(person_ids),
                (WorkingSchedule.effective_start_date.is_(None))
                | (WorkingSchedule.effective_start_date <= end_date),
                (WorkingSchedule.effective_end_date.is_(None))
                | (WorkingSchedule.effective_end_date >= start_date),
            )
            .options(selectinload(WorkingSchedule.entries))
        )
        return list(self.session.scalars(stmt))

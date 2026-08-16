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

    def get_by_external_id(self, external_id: str) -> WorkingSchedule | None:
        return self.session.scalar(
            select(WorkingSchedule)
            .where(WorkingSchedule.external_id == external_id)
            .options(selectinload(WorkingSchedule.entries))
        )

    def list_by_external_ids(self, external_ids: list[str]) -> list[WorkingSchedule]:
        """Batched lookup for Phase 6 import identity resolution. entries is
        eager-loaded since diffing always needs it (see
        app/domain/import_export_diff.py::WorkingScheduleFact)."""
        if not external_ids:
            return []
        return list(
            self.session.scalars(
                select(WorkingSchedule)
                .where(WorkingSchedule.external_id.in_(external_ids))
                .options(selectinload(WorkingSchedule.entries))
            )
        )

    def list_all_for_people(self, person_ids: list[uuid.UUID]) -> list[WorkingSchedule]:
        """Every schedule for any of person_ids, regardless of effective
        date range (unlike list_for_people, which only returns schedules
        intersecting a query range) — used by Phase 6 import to pre-check
        overlap against a person's complete existing schedule set before
        writing anything."""
        if not person_ids:
            return []
        return list(
            self.session.scalars(
                select(WorkingSchedule)
                .where(WorkingSchedule.person_id.in_(person_ids))
                .options(selectinload(WorkingSchedule.entries))
            )
        )

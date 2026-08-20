import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.working_schedule import WorkingSchedule
from app.repositories.base import BaseRepository


class WorkingScheduleRepository(BaseRepository[WorkingSchedule]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = WorkingSchedule

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> WorkingSchedule | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(WorkingSchedule)
            .where(WorkingSchedule.id == id_, WorkingSchedule.organization_id == organization_id)
            .options(selectinload(WorkingSchedule.entries))
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[WorkingSchedule], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(WorkingSchedule)
                .where(WorkingSchedule.organization_id == organization_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(WorkingSchedule)
                .where(WorkingSchedule.organization_id == organization_id)
                .options(selectinload(WorkingSchedule.entries))
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def list_for_person(
        self, person_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[WorkingSchedule]:
        return list(
            self.session.scalars(
                select(WorkingSchedule).where(
                    WorkingSchedule.person_id == person_id,
                    WorkingSchedule.organization_id == organization_id,
                )
            )
        )

    def list_for_people(
        self,
        person_ids: list[uuid.UUID],
        start_date: date,
        end_date: date,
        organization_id: uuid.UUID,
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
                WorkingSchedule.organization_id == organization_id,
                (WorkingSchedule.effective_start_date.is_(None))
                | (WorkingSchedule.effective_start_date <= end_date),
                (WorkingSchedule.effective_end_date.is_(None))
                | (WorkingSchedule.effective_end_date >= start_date),
            )
            .options(selectinload(WorkingSchedule.entries))
        )
        return list(self.session.scalars(stmt))

    def get_by_external_id(
        self, external_id: str, organization_id: uuid.UUID
    ) -> WorkingSchedule | None:
        return self.session.scalar(
            select(WorkingSchedule)
            .where(
                WorkingSchedule.external_id == external_id,
                WorkingSchedule.organization_id == organization_id,
            )
            .options(selectinload(WorkingSchedule.entries))
        )

    def list_by_external_ids(
        self, external_ids: list[str], organization_id: uuid.UUID
    ) -> list[WorkingSchedule]:
        """Batched lookup for Phase 6 import identity resolution. entries is
        eager-loaded since diffing always needs it (see
        app/domain/import_export_diff.py::WorkingScheduleFact)."""
        if not external_ids:
            return []
        return list(
            self.session.scalars(
                select(WorkingSchedule)
                .where(
                    WorkingSchedule.external_id.in_(external_ids),
                    WorkingSchedule.organization_id == organization_id,
                )
                .options(selectinload(WorkingSchedule.entries))
            )
        )

    def list_all_for_people(
        self, person_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[WorkingSchedule]:
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
                .where(
                    WorkingSchedule.person_id.in_(person_ids),
                    WorkingSchedule.organization_id == organization_id,
                )
                .options(selectinload(WorkingSchedule.entries))
            )
        )

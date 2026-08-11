import uuid
from datetime import date

from sqlalchemy import func, select

from app.models.allocation import Allocation
from app.repositories.base import BaseRepository


class AllocationRepository(BaseRepository[Allocation]):
    model = Allocation

    def list_filtered(
        self,
        *,
        person_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Allocation], int]:
        stmt = select(Allocation)
        if person_id is not None:
            stmt = stmt.where(Allocation.person_id == person_id)
        if project_id is not None:
            stmt = stmt.where(Allocation.project_id == project_id)

        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.session.scalars(stmt.order_by(Allocation.start_date).limit(limit).offset(offset))
        )
        return items, total

    def list_for_people(
        self, person_ids: list[uuid.UUID], start_date: date, end_date: date
    ) -> list[Allocation]:
        """Allocations for any of person_ids overlapping [start_date, end_date],
        one query for the whole batch — see WorkingScheduleRepository.list_for_people."""
        if not person_ids:
            return []
        stmt = select(Allocation).where(
            Allocation.person_id.in_(person_ids),
            Allocation.start_date <= end_date,
            Allocation.end_date >= start_date,
        )
        return list(self.session.scalars(stmt))

    def list_for_project(
        self, project_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[Allocation]:
        """Allocations on project_id overlapping [start_date, end_date] — feeds
        project demand (app/services/capacity.py CapacityService.get_project_demand)."""
        stmt = select(Allocation).where(
            Allocation.project_id == project_id,
            Allocation.start_date <= end_date,
            Allocation.end_date >= start_date,
        )
        return list(self.session.scalars(stmt))

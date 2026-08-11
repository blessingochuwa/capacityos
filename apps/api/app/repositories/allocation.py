import uuid

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

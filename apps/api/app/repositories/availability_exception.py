import uuid
from datetime import date

from sqlalchemy import func, select

from app.models.availability_exception import AvailabilityException
from app.repositories.base import BaseRepository


class AvailabilityExceptionRepository(BaseRepository[AvailabilityException]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = AvailabilityException

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> AvailabilityException | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(AvailabilityException).where(
                AvailabilityException.id == id_,
                AvailabilityException.organization_id == organization_id,
            )
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[AvailabilityException], int]:
        return self.list_filtered(organization_id, limit=limit, offset=offset)

    def list_filtered(
        self,
        organization_id: uuid.UUID,
        *,
        person_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AvailabilityException], int]:
        stmt = select(AvailabilityException).where(
            AvailabilityException.organization_id == organization_id
        )
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
        self,
        person_ids: list[uuid.UUID],
        start_date: date,
        end_date: date,
        organization_id: uuid.UUID,
    ) -> list[AvailabilityException]:
        """Exceptions for any of person_ids overlapping [start_date, end_date],
        one query for the whole batch — see WorkingScheduleRepository.list_for_people."""
        if not person_ids:
            return []
        stmt = select(AvailabilityException).where(
            AvailabilityException.person_id.in_(person_ids),
            AvailabilityException.organization_id == organization_id,
            AvailabilityException.start_date <= end_date,
            AvailabilityException.end_date >= start_date,
        )
        return list(self.session.scalars(stmt))

    def get_by_external_id(
        self, external_id: str, organization_id: uuid.UUID
    ) -> AvailabilityException | None:
        return self.session.scalar(
            select(AvailabilityException).where(
                AvailabilityException.external_id == external_id,
                AvailabilityException.organization_id == organization_id,
            )
        )

    def list_by_external_ids(
        self, external_ids: list[str], organization_id: uuid.UUID
    ) -> list[AvailabilityException]:
        """Batched lookup for Phase 6 import identity resolution."""
        if not external_ids:
            return []
        return list(
            self.session.scalars(
                select(AvailabilityException).where(
                    AvailabilityException.external_id.in_(external_ids),
                    AvailabilityException.organization_id == organization_id,
                )
            )
        )

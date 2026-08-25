import uuid

from sqlalchemy import func, select

from app.models.portfolio_snapshot import PortfolioSnapshot
from app.repositories.base import BaseRepository


class PortfolioSnapshotRepository(BaseRepository[PortfolioSnapshot]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = PortfolioSnapshot

    def get(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, id_: uuid.UUID, organization_id: uuid.UUID
    ) -> PortfolioSnapshot | None:
        return self.session.scalar(
            select(PortfolioSnapshot).where(
                PortfolioSnapshot.id == id_,
                PortfolioSnapshot.organization_id == organization_id,
            )
        )

    def list_(
        self,
        organization_id: uuid.UUID,
        *,
        framework_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PortfolioSnapshot], int]:
        """Most recent first — a history list, matching AuditEvent's own
        newest-first convention."""
        filters = [PortfolioSnapshot.organization_id == organization_id]
        if framework_id is not None:
            filters.append(PortfolioSnapshot.framework_id == framework_id)

        total = (
            self.session.scalar(select(func.count()).select_from(PortfolioSnapshot).where(*filters))
            or 0
        )
        items = list(
            self.session.scalars(
                select(PortfolioSnapshot)
                .where(*filters)
                .order_by(PortfolioSnapshot.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

import uuid

from sqlalchemy import func, select

from app.models.enums import RiskStatus
from app.models.risk import Risk
from app.repositories.base import BaseRepository


class RiskRepository(BaseRepository[Risk]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = Risk

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> Risk | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(Risk).where(Risk.id == id_, Risk.organization_id == organization_id)
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[Risk], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(Risk)
                .where(Risk.organization_id == organization_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(Risk)
                .where(Risk.organization_id == organization_id)
                .order_by(Risk.created_at)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def list_for_project(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> list[Risk]:
        return list(
            self.session.scalars(
                select(Risk)
                .where(Risk.project_id == project_id, Risk.organization_id == organization_id)
                .order_by(Risk.created_at)
            )
        )

    def list_open_for_project(
        self, project_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[Risk]:
        """Every risk NOT closed — "open" here means "still live" (open,
        mitigating, or monitoring), not literally RiskStatus.OPEN. Feeds
        the Insights signal builder (app/services/insight_service.py),
        which never surfaces a signal for a closed risk (see
        app/domain/risk.py::classify_risk_signal)."""
        return list(
            self.session.scalars(
                select(Risk).where(
                    Risk.project_id == project_id,
                    Risk.organization_id == organization_id,
                    Risk.status != RiskStatus.CLOSED,
                )
            )
        )

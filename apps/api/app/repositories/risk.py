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

    def get_by_external_id(self, external_id: str, organization_id: uuid.UUID) -> Risk | None:
        return self.session.scalar(
            select(Risk).where(
                Risk.external_id == external_id, Risk.organization_id == organization_id
            )
        )

    def list_by_external_ids(
        self, external_ids: list[str], organization_id: uuid.UUID
    ) -> list[Risk]:
        """Batched lookup for Phase 36 import identity resolution."""
        if not external_ids:
            return []
        return list(
            self.session.scalars(
                select(Risk).where(
                    Risk.external_id.in_(external_ids), Risk.organization_id == organization_id
                )
            )
        )

    def list_filtered(
        self,
        organization_id: uuid.UUID,
        *,
        project_id: uuid.UUID | None = None,
        status: RiskStatus | None = None,
    ) -> list[Risk]:
        """Every risk across the ENTIRE organization matching the given
        filters — the org-wide counterpart to list_for_project (Phase 47,
        the org-wide Risk register). `exposure` is deliberately NOT a
        parameter here: it is never a persisted column (see the Risk
        model's docstring), so this repository stays SQL-filtering only —
        RiskService.list_for_organization applies the exposure filter (and
        pagination) afterward, computing exposure through the same single
        source of truth (calculate_risk_exposure) every other Risk read
        path already uses, rather than duplicating the probability x
        impact lookup table into a second, SQL-side form."""
        stmt = select(Risk).where(Risk.organization_id == organization_id)
        if project_id is not None:
            stmt = stmt.where(Risk.project_id == project_id)
        if status is not None:
            stmt = stmt.where(Risk.status == status)
        return list(self.session.scalars(stmt.order_by(Risk.created_at)))

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

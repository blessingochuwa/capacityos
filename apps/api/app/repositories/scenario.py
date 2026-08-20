import uuid

from sqlalchemy import func, select

from app.models.enums import ScenarioStatus
from app.models.scenario import Scenario, ScenarioOperation
from app.repositories.base import BaseRepository


class ScenarioRepository(BaseRepository[Scenario]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = Scenario

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> Scenario | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(Scenario).where(
                Scenario.id == id_, Scenario.organization_id == organization_id
            )
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[Scenario], int]:
        return self.list_filtered(organization_id, limit=limit, offset=offset)

    def list_filtered(
        self,
        organization_id: uuid.UUID,
        *,
        status: ScenarioStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Scenario], int]:
        stmt = select(Scenario).where(Scenario.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(Scenario.status == status)

        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.session.scalars(
                stmt.order_by(Scenario.created_at.desc()).limit(limit).offset(offset)
            )
        )
        return items, total


class ScenarioOperationRepository(BaseRepository[ScenarioOperation]):
    model = ScenarioOperation

    def list_for_scenario(self, scenario_id: uuid.UUID) -> list[ScenarioOperation]:
        """Every operation for scenario_id, in application order — the same
        order app.domain.scenario.apply_scenario_operations relies on."""
        stmt = (
            select(ScenarioOperation)
            .where(ScenarioOperation.scenario_id == scenario_id)
            .order_by(ScenarioOperation.sequence)
        )
        return list(self.session.scalars(stmt))

    def list_for_scenario_page(
        self, scenario_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[ScenarioOperation], int]:
        stmt = select(ScenarioOperation).where(ScenarioOperation.scenario_id == scenario_id)
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.session.scalars(
                stmt.order_by(ScenarioOperation.sequence).limit(limit).offset(offset)
            )
        )
        return items, total

    def get_for_scenario(
        self, scenario_id: uuid.UUID, operation_id: uuid.UUID
    ) -> ScenarioOperation | None:
        """Scopes the lookup to scenario_id so PATCH/DELETE on
        /scenarios/{scenario_id}/operations/{operation_id} can't act on an
        operation belonging to a different scenario."""
        return self.session.scalar(
            select(ScenarioOperation).where(
                ScenarioOperation.id == operation_id, ScenarioOperation.scenario_id == scenario_id
            )
        )

    def next_sequence(self, scenario_id: uuid.UUID) -> int:
        """max(sequence) + 1 for scenario_id (0 if it has none yet) — not a
        row count, because a deleted operation would make count() collide
        with a still-existing sequence number and violate
        uq_scenario_operation_sequence."""
        current_max = self.session.scalar(
            select(func.max(ScenarioOperation.sequence)).where(
                ScenarioOperation.scenario_id == scenario_id
            )
        )
        return 0 if current_max is None else current_max + 1

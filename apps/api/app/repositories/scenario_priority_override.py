import uuid

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.scenario_priority_override import ScenarioPriorityOverride
from app.repositories.base import BaseRepository


class ScenarioPriorityOverrideRepository(BaseRepository[ScenarioPriorityOverride]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = ScenarioPriorityOverride

    def get(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, id_: uuid.UUID, organization_id: uuid.UUID
    ) -> ScenarioPriorityOverride | None:
        return self.session.scalar(
            select(ScenarioPriorityOverride)
            .options(
                joinedload(ScenarioPriorityOverride.project),
                joinedload(ScenarioPriorityOverride.framework),
            )
            .where(
                ScenarioPriorityOverride.id == id_,
                ScenarioPriorityOverride.organization_id == organization_id,
            )
        )

    def get_by_natural_key(
        self,
        scenario_id: uuid.UUID,
        project_id: uuid.UUID,
        framework_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ScenarioPriorityOverride | None:
        return self.session.scalar(
            select(ScenarioPriorityOverride).where(
                ScenarioPriorityOverride.scenario_id == scenario_id,
                ScenarioPriorityOverride.project_id == project_id,
                ScenarioPriorityOverride.framework_id == framework_id,
                ScenarioPriorityOverride.organization_id == organization_id,
            )
        )

    def list_for_scenario(
        self, scenario_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[ScenarioPriorityOverride]:
        return list(
            self.session.scalars(
                select(ScenarioPriorityOverride)
                .options(
                    joinedload(ScenarioPriorityOverride.project),
                    joinedload(ScenarioPriorityOverride.framework),
                )
                .where(
                    ScenarioPriorityOverride.scenario_id == scenario_id,
                    ScenarioPriorityOverride.organization_id == organization_id,
                )
                .order_by(ScenarioPriorityOverride.created_at)
            )
        )

    def list_for_scenario_and_framework(
        self, scenario_id: uuid.UUID, framework_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[ScenarioPriorityOverride]:
        return list(
            self.session.scalars(
                select(ScenarioPriorityOverride).where(
                    ScenarioPriorityOverride.scenario_id == scenario_id,
                    ScenarioPriorityOverride.framework_id == framework_id,
                    ScenarioPriorityOverride.organization_id == organization_id,
                )
            )
        )

import uuid

from sqlalchemy import select

from app.models.prioritization_criterion import PrioritizationCriterion
from app.repositories.base import BaseRepository


class PrioritizationCriterionRepository(BaseRepository[PrioritizationCriterion]):
    """Organization-scoped (Phase 12), reached only through its owning
    PrioritizationFramework in practice (list_for_framework), plus a
    direct-by-id lookup for update/delete of a single criterion."""

    model = PrioritizationCriterion

    def get(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, id_: uuid.UUID, organization_id: uuid.UUID
    ) -> PrioritizationCriterion | None:
        return self.session.scalar(
            select(PrioritizationCriterion).where(
                PrioritizationCriterion.id == id_,
                PrioritizationCriterion.organization_id == organization_id,
            )
        )

    def list_for_framework(
        self, framework_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[PrioritizationCriterion]:
        return list(
            self.session.scalars(
                select(PrioritizationCriterion)
                .where(
                    PrioritizationCriterion.framework_id == framework_id,
                    PrioritizationCriterion.organization_id == organization_id,
                )
                .order_by(PrioritizationCriterion.sequence)
            )
        )

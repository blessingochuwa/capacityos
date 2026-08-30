import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.prioritization_framework import PrioritizationFramework
from app.repositories.base import BaseRepository


class PrioritizationFrameworkRepository(BaseRepository[PrioritizationFramework]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = PrioritizationFramework

    def get(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, id_: uuid.UUID, organization_id: uuid.UUID
    ) -> PrioritizationFramework | None:
        return self.session.scalar(
            select(PrioritizationFramework)
            .options(selectinload(PrioritizationFramework.criteria))
            .where(
                PrioritizationFramework.id == id_,
                PrioritizationFramework.organization_id == organization_id,
            )
        )

    def get_by_name(
        self, name: str, organization_id: uuid.UUID
    ) -> PrioritizationFramework | None:
        return self.session.scalar(
            select(PrioritizationFramework).where(
                PrioritizationFramework.name == name,
                PrioritizationFramework.organization_id == organization_id,
            )
        )

    def list_by_ids(
        self, ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[PrioritizationFramework]:
        """Batched lookup for Phase 36 import identity resolution."""
        if not ids:
            return []
        return list(
            self.session.scalars(
                select(PrioritizationFramework)
                .options(selectinload(PrioritizationFramework.criteria))
                .where(
                    PrioritizationFramework.id.in_(ids),
                    PrioritizationFramework.organization_id == organization_id,
                )
            )
        )

    def list_by_names(
        self, names: list[str], organization_id: uuid.UUID
    ) -> list[PrioritizationFramework]:
        """Batched lookup for Phase 36 import identity resolution."""
        if not names:
            return []
        return list(
            self.session.scalars(
                select(PrioritizationFramework)
                .options(selectinload(PrioritizationFramework.criteria))
                .where(
                    PrioritizationFramework.name.in_(names),
                    PrioritizationFramework.organization_id == organization_id,
                )
            )
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        organization_id: uuid.UUID,
        *,
        is_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PrioritizationFramework], int]:
        stmt = select(PrioritizationFramework).where(
            PrioritizationFramework.organization_id == organization_id
        )
        if is_active is not None:
            stmt = stmt.where(PrioritizationFramework.is_active == is_active)

        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.session.scalars(
                stmt.options(selectinload(PrioritizationFramework.criteria))
                .order_by(PrioritizationFramework.name)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

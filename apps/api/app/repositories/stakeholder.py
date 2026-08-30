import uuid

from sqlalchemy import func, select

from app.models.stakeholder import Stakeholder
from app.repositories.base import BaseRepository


class StakeholderRepository(BaseRepository[Stakeholder]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = Stakeholder

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> Stakeholder | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(Stakeholder).where(
                Stakeholder.id == id_, Stakeholder.organization_id == organization_id
            )
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[Stakeholder], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(Stakeholder)
                .where(Stakeholder.organization_id == organization_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(Stakeholder)
                .where(Stakeholder.organization_id == organization_id)
                .order_by(Stakeholder.created_at)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def list_for_project(
        self, project_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[Stakeholder]:
        return list(
            self.session.scalars(
                select(Stakeholder)
                .where(
                    Stakeholder.project_id == project_id,
                    Stakeholder.organization_id == organization_id,
                )
                .order_by(Stakeholder.created_at)
            )
        )

    def list_for_projects(
        self, project_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[Stakeholder]:
        """Batched — one query for the whole id list, used by Phase 36
        import identity resolution instead of one list_for_project call
        per row (matches ProjectSkillRequirementRepository.list_for_projects)."""
        if not project_ids:
            return []
        return list(
            self.session.scalars(
                select(Stakeholder).where(
                    Stakeholder.project_id.in_(project_ids),
                    Stakeholder.organization_id == organization_id,
                )
            )
        )

    def get_by_project_and_person(
        self, project_id: uuid.UUID, person_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Stakeholder | None:
        return self.session.scalar(
            select(Stakeholder).where(
                Stakeholder.project_id == project_id,
                Stakeholder.person_id == person_id,
                Stakeholder.organization_id == organization_id,
            )
        )

import uuid

from sqlalchemy import func, select

from app.models.enums import (
    StakeholderDecisionAuthority,
    StakeholderInfluence,
    StakeholderInterest,
)
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

    def list_filtered(
        self,
        organization_id: uuid.UUID,
        *,
        project_id: uuid.UUID | None = None,
        influence: StakeholderInfluence | None = None,
        interest: StakeholderInterest | None = None,
        decision_authority: StakeholderDecisionAuthority | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Stakeholder], int]:
        """Every stakeholder across the ENTIRE organization matching the
        given filters — the org-wide counterpart to list_for_project
        (Phase 48, the org-wide Stakeholder register). Unlike
        RiskRepository.list_filtered, every filter here is a persisted,
        CHECK-constrained column (Stakeholder has no derived field like
        Risk.exposure), so filtering, counting, and pagination all happen
        in SQL — `total` is a COUNT over the same WHERE clause the page
        query uses, never len() of a Python-side list. Ordered by
        (created_at, id) so a created_at tie can never make a row appear
        on two pages or on none."""
        conditions = [Stakeholder.organization_id == organization_id]
        if project_id is not None:
            conditions.append(Stakeholder.project_id == project_id)
        if influence is not None:
            conditions.append(Stakeholder.influence == influence)
        if interest is not None:
            conditions.append(Stakeholder.interest == interest)
        if decision_authority is not None:
            conditions.append(Stakeholder.decision_authority == decision_authority)

        total = (
            self.session.scalar(
                select(func.count()).select_from(Stakeholder).where(*conditions)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(Stakeholder)
                .where(*conditions)
                .order_by(Stakeholder.created_at, Stakeholder.id)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

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

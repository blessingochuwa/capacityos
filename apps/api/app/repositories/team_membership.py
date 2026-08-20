import uuid

from sqlalchemy import func, select

from app.models.team_membership import TeamMembership
from app.repositories.base import BaseRepository


class TeamMembershipRepository(BaseRepository[TeamMembership]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = TeamMembership

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> TeamMembership | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(TeamMembership).where(
                TeamMembership.id == id_, TeamMembership.organization_id == organization_id
            )
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[TeamMembership], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(TeamMembership)
                .where(TeamMembership.organization_id == organization_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(TeamMembership)
                .where(TeamMembership.organization_id == organization_id)
                .order_by(TeamMembership.created_at)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def get_by_person_and_team(
        self, person_id: uuid.UUID, team_id: uuid.UUID, organization_id: uuid.UUID
    ) -> TeamMembership | None:
        return self.session.scalar(
            select(TeamMembership).where(
                TeamMembership.person_id == person_id,
                TeamMembership.team_id == team_id,
                TeamMembership.organization_id == organization_id,
            )
        )

    def list_for_team(
        self, team_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[TeamMembership]:
        return list(
            self.session.scalars(
                select(TeamMembership)
                .where(
                    TeamMembership.team_id == team_id,
                    TeamMembership.organization_id == organization_id,
                )
                .order_by(TeamMembership.created_at)
            )
        )

    def list_for_people(
        self, person_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[TeamMembership]:
        """Memberships for any of person_ids, one query for the whole batch
        — same batched pattern as AllocationRepository.list_for_people etc.
        Used by scenario impact analysis to report which teams are affected
        (app/services/scenario_calculation.py) without a query per person."""
        if not person_ids:
            return []
        return list(
            self.session.scalars(
                select(TeamMembership).where(
                    TeamMembership.person_id.in_(person_ids),
                    TeamMembership.organization_id == organization_id,
                )
            )
        )

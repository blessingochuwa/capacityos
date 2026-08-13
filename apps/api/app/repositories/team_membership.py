import uuid

from sqlalchemy import select

from app.models.team_membership import TeamMembership
from app.repositories.base import BaseRepository


class TeamMembershipRepository(BaseRepository[TeamMembership]):
    model = TeamMembership

    def get_by_person_and_team(
        self, person_id: uuid.UUID, team_id: uuid.UUID
    ) -> TeamMembership | None:
        return self.session.scalar(
            select(TeamMembership).where(
                TeamMembership.person_id == person_id, TeamMembership.team_id == team_id
            )
        )

    def list_for_team(self, team_id: uuid.UUID) -> list[TeamMembership]:
        return list(
            self.session.scalars(
                select(TeamMembership)
                .where(TeamMembership.team_id == team_id)
                .order_by(TeamMembership.created_at)
            )
        )

    def list_for_people(self, person_ids: list[uuid.UUID]) -> list[TeamMembership]:
        """Memberships for any of person_ids, one query for the whole batch
        — same batched pattern as AllocationRepository.list_for_people etc.
        Used by scenario impact analysis to report which teams are affected
        (app/services/scenario_calculation.py) without a query per person."""
        if not person_ids:
            return []
        return list(
            self.session.scalars(
                select(TeamMembership).where(TeamMembership.person_id.in_(person_ids))
            )
        )

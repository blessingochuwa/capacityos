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

import uuid

from sqlalchemy import select

from app.models.team_access_grant import TeamAccessGrant
from app.repositories.base import BaseRepository


class TeamAccessGrantRepository(BaseRepository[TeamAccessGrant]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = TeamAccessGrant

    def get_by_user_and_team(
        self, user_id: uuid.UUID, team_id: uuid.UUID, organization_id: uuid.UUID
    ) -> TeamAccessGrant | None:
        return self.session.scalar(
            select(TeamAccessGrant).where(
                TeamAccessGrant.user_id == user_id,
                TeamAccessGrant.team_id == team_id,
                TeamAccessGrant.organization_id == organization_id,
            )
        )

    def exists(self, user_id: uuid.UUID, team_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
        return self.get_by_user_and_team(user_id, team_id, organization_id) is not None

    def list_for_team(
        self, team_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[TeamAccessGrant]:
        return list(
            self.session.scalars(
                select(TeamAccessGrant)
                .where(
                    TeamAccessGrant.team_id == team_id,
                    TeamAccessGrant.organization_id == organization_id,
                )
                .order_by(TeamAccessGrant.created_at)
            )
        )

    def list_for_user(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[TeamAccessGrant]:
        return list(
            self.session.scalars(
                select(TeamAccessGrant)
                .where(
                    TeamAccessGrant.user_id == user_id,
                    TeamAccessGrant.organization_id == organization_id,
                )
                .order_by(TeamAccessGrant.created_at)
            )
        )

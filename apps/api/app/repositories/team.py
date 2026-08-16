import uuid

from sqlalchemy import select

from app.models.team import Team
from app.repositories.base import BaseRepository


class TeamRepository(BaseRepository[Team]):
    model = Team

    def get_by_name(self, name: str) -> Team | None:
        return self.session.scalar(select(Team).where(Team.name == name))

    def list_by_ids(self, team_ids: list[uuid.UUID]) -> list[Team]:
        """Batched lookup for a known set of ids — mirrors
        PersonRepository.list_by_ids. Used by Phase 6 import reference
        resolution."""
        if not team_ids:
            return []
        return list(self.session.scalars(select(Team).where(Team.id.in_(team_ids))))

    def list_by_names(self, names: list[str]) -> list[Team]:
        """Batched lookup for Phase 6 import identity resolution."""
        if not names:
            return []
        return list(self.session.scalars(select(Team).where(Team.name.in_(names))))

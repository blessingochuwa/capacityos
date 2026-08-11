from sqlalchemy import select

from app.models.team import Team
from app.repositories.base import BaseRepository


class TeamRepository(BaseRepository[Team]):
    model = Team

    def get_by_name(self, name: str) -> Team | None:
        return self.session.scalar(select(Team).where(Team.name == name))

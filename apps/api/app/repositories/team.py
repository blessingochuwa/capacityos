import uuid

from sqlalchemy import func, select

from app.models.team import Team
from app.repositories.base import BaseRepository


class TeamRepository(BaseRepository[Team]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = Team

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> Team | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(Team).where(Team.id == id_, Team.organization_id == organization_id)
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[Team], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(Team)
                .where(Team.organization_id == organization_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(Team)
                .where(Team.organization_id == organization_id)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def get_by_name(self, name: str, organization_id: uuid.UUID) -> Team | None:
        return self.session.scalar(
            select(Team).where(Team.name == name, Team.organization_id == organization_id)
        )

    def list_by_ids(self, team_ids: list[uuid.UUID], organization_id: uuid.UUID) -> list[Team]:
        """Batched lookup for a known set of ids — mirrors
        PersonRepository.list_by_ids. Used by Phase 6 import reference
        resolution."""
        if not team_ids:
            return []
        return list(
            self.session.scalars(
                select(Team).where(
                    Team.id.in_(team_ids), Team.organization_id == organization_id
                )
            )
        )

    def list_by_names(self, names: list[str], organization_id: uuid.UUID) -> list[Team]:
        """Batched lookup for Phase 6 import identity resolution."""
        if not names:
            return []
        return list(
            self.session.scalars(
                select(Team).where(
                    Team.name.in_(names), Team.organization_id == organization_id
                )
            )
        )

import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.team import Team
from app.repositories.team import TeamRepository
from app.schemas.team import TeamCreate, TeamUpdate


class TeamService:
    """Organization-scoped (Phase 12) — see app/services/person.py's
    docstring for the general pattern this follows."""

    def __init__(self, repository: TeamRepository) -> None:
        self.repository = repository

    def create(self, organization_id: uuid.UUID, data: TeamCreate) -> Team:
        if self.repository.get_by_name(data.name, organization_id) is not None:
            raise ConflictError(f"A team named '{data.name}' already exists.")
        team = Team(organization_id=organization_id, name=data.name, description=data.description)
        return self.repository.add(team)

    def get(self, organization_id: uuid.UUID, team_id: uuid.UUID) -> Team:
        team = self.repository.get(team_id, organization_id)
        if team is None:
            raise NotFoundError("Team", team_id)
        return team

    def list(
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[Team], int]:
        return self.repository.list(organization_id, limit=limit, offset=offset)

    def update(self, organization_id: uuid.UUID, team_id: uuid.UUID, data: TeamUpdate) -> Team:
        team = self.get(organization_id, team_id)
        updates = data.model_dump(exclude_unset=True)

        new_name = updates.get("name")
        if new_name is not None and new_name != team.name:
            existing = self.repository.get_by_name(new_name, organization_id)
            if existing is not None and existing.id != team.id:
                raise ConflictError(f"A team named '{new_name}' already exists.")

        for field, value in updates.items():
            setattr(team, field, value)
        self.repository.session.flush()
        return team

    def delete(self, organization_id: uuid.UUID, team_id: uuid.UUID) -> None:
        self.repository.delete(self.get(organization_id, team_id))

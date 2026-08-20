import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.team_membership import TeamMembership
from app.repositories.person import PersonRepository
from app.repositories.team import TeamRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.schemas.team_membership import TeamMembershipCreate


class TeamMembershipService:
    """Organization-scoped (Phase 12) — person_id/team_id are guaranteed
    same-organization by construction, same reasoning as
    PersonSkillService (see its docstring)."""

    def __init__(
        self,
        membership_repository: TeamMembershipRepository,
        person_repository: PersonRepository,
        team_repository: TeamRepository,
    ) -> None:
        self.membership_repository = membership_repository
        self.person_repository = person_repository
        self.team_repository = team_repository

    def add_member(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, data: TeamMembershipCreate
    ) -> TeamMembership:
        if self.team_repository.get(team_id, organization_id) is None:
            raise NotFoundError("Team", team_id)
        if self.person_repository.get(data.person_id, organization_id) is None:
            raise NotFoundError("Person", data.person_id)
        existing = self.membership_repository.get_by_person_and_team(
            data.person_id, team_id, organization_id
        )
        if existing is not None:
            raise ConflictError("This person is already a member of this team.")

        membership = TeamMembership(
            organization_id=organization_id, person_id=data.person_id, team_id=team_id
        )
        return self.membership_repository.add(membership)

    def list_members(self, organization_id: uuid.UUID, team_id: uuid.UUID) -> list[TeamMembership]:
        if self.team_repository.get(team_id, organization_id) is None:
            raise NotFoundError("Team", team_id)
        return self.membership_repository.list_for_team(team_id, organization_id)

    def remove_member(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, person_id: uuid.UUID
    ) -> None:
        membership = self.membership_repository.get_by_person_and_team(
            person_id, team_id, organization_id
        )
        if membership is None:
            raise NotFoundError("TeamMembership", f"person={person_id} team={team_id}")
        self.membership_repository.delete(membership)

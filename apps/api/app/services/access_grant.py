import uuid

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.domain.authorization import Permission, ResourceScope, has_permission
from app.models.enums import AuditAction, AuditOutcome, MembershipStatus
from app.models.organization_membership import OrganizationMembership
from app.models.project_access_grant import ProjectAccessGrant
from app.models.team_access_grant import TeamAccessGrant
from app.models.user import User
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_access_grant import ProjectAccessGrantRepository
from app.repositories.team import TeamRepository
from app.repositories.team_access_grant import TeamAccessGrantRepository
from app.services.audit import AuditService


class AccessGrantService:
    """Instance-level resource authorization (Phase 11), now organization-
    scoped (Phase 12) — the one place a Manager's Team/Project write
    authority is checked against an explicit grant, and the one place
    grants are created/removed/listed. See
    docs/adr/0011-instance-level-resource-authorization.md and
    docs/adr/0012-organizations-multi-tenancy.md.

    enforce_team_access/enforce_project_access are the single call site
    every authorization dependency (app/api/deps.py::require_team_access /
    require_project_access) AND every inline invocation (allocations.py's
    body/existing-row-resolved routes) goes through — the decision logic is
    never reimplemented per route.
    """

    def __init__(
        self,
        team_grants: TeamAccessGrantRepository,
        project_grants: ProjectAccessGrantRepository,
        teams: TeamRepository,
        projects: ProjectRepository,
        memberships: OrganizationMembershipRepository,
    ) -> None:
        self.team_grants = team_grants
        self.project_grants = project_grants
        self.teams = teams
        self.projects = projects
        self.memberships = memberships

    # --- authorization decision -------------------------------------------------

    def enforce_team_access(
        self,
        user: User,
        membership: OrganizationMembership,
        team_id: uuid.UUID,
        permission: Permission,
        *,
        audit_service: AuditService,
        request_id: str | None,
    ) -> None:
        granted = self.team_grants.exists(user.id, team_id, membership.organization_id)
        if has_permission(membership.role, permission, resource=ResourceScope(granted=granted)):
            return
        audit_service.record(
            actor_user_id=user.id,
            actor_email=user.email,
            action=AuditAction.RESOURCE_ACCESS_DENIED,
            outcome=AuditOutcome.DENIED,
            resource_type="team",
            resource_id=str(team_id),
            request_id=request_id,
            organization_id=membership.organization_id,
            metadata={"permission": permission.value, "role": membership.role.value},
        )
        raise ForbiddenError(f"You do not have access to manage this team ({team_id}).")

    def enforce_project_access(
        self,
        user: User,
        membership: OrganizationMembership,
        project_id: uuid.UUID,
        permission: Permission,
        *,
        audit_service: AuditService,
        request_id: str | None,
    ) -> None:
        granted = self.project_grants.exists(user.id, project_id, membership.organization_id)
        if has_permission(membership.role, permission, resource=ResourceScope(granted=granted)):
            return
        audit_service.record(
            actor_user_id=user.id,
            actor_email=user.email,
            action=AuditAction.RESOURCE_ACCESS_DENIED,
            outcome=AuditOutcome.DENIED,
            resource_type="project",
            resource_id=str(project_id),
            request_id=request_id,
            organization_id=membership.organization_id,
            metadata={"permission": permission.value, "role": membership.role.value},
        )
        raise ForbiddenError(f"You do not have access to manage this project ({project_id}).")

    # --- grant/revoke/list CRUD --------------------------------------------------

    def grant_team_access(
        self,
        organization_id: uuid.UUID,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        granted_by: User,
    ) -> TeamAccessGrant:
        if self.teams.get(team_id, organization_id) is None:
            raise NotFoundError("Team", team_id)
        target_membership = self.memberships.get_by_user_and_org(user_id, organization_id)
        if target_membership is None or target_membership.status != MembershipStatus.ACTIVE:
            # Not ForbiddenError — a user_id from a different organization
            # (or with no membership here at all) must look exactly like a
            # nonexistent user, never confirming they exist elsewhere.
            raise NotFoundError("User", user_id)
        if self.team_grants.exists(user_id, team_id, organization_id):
            raise ConflictError("This user already has access to this team.")
        grant = TeamAccessGrant(
            organization_id=organization_id,
            user_id=user_id,
            team_id=team_id,
            granted_by_user_id=granted_by.id,
        )
        return self.team_grants.add(grant)

    def revoke_team_access(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        grant = self.team_grants.get_by_user_and_team(user_id, team_id, organization_id)
        if grant is None:
            raise NotFoundError("TeamAccessGrant", f"user={user_id} team={team_id}")
        self.team_grants.delete(grant)

    def list_team_grants(
        self, organization_id: uuid.UUID, team_id: uuid.UUID
    ) -> list[TeamAccessGrant]:
        if self.teams.get(team_id, organization_id) is None:
            raise NotFoundError("Team", team_id)
        return self.team_grants.list_for_team(team_id, organization_id)

    def grant_project_access(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        granted_by: User,
    ) -> ProjectAccessGrant:
        if self.projects.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)
        target_membership = self.memberships.get_by_user_and_org(user_id, organization_id)
        if target_membership is None or target_membership.status != MembershipStatus.ACTIVE:
            raise NotFoundError("User", user_id)
        if self.project_grants.exists(user_id, project_id, organization_id):
            raise ConflictError("This user already has access to this project.")
        grant = ProjectAccessGrant(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            granted_by_user_id=granted_by.id,
        )
        return self.project_grants.add(grant)

    def revoke_project_access(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        grant = self.project_grants.get_by_user_and_project(user_id, project_id, organization_id)
        if grant is None:
            raise NotFoundError("ProjectAccessGrant", f"user={user_id} project={project_id}")
        self.project_grants.delete(grant)

    def list_project_grants(
        self, organization_id: uuid.UUID, project_id: uuid.UUID
    ) -> list[ProjectAccessGrant]:
        if self.projects.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)
        return self.project_grants.list_for_project(project_id, organization_id)

    # --- current-user accessible-ids (feeds /auth/me for the frontend) ----------

    def accessible_team_ids(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[uuid.UUID]:
        return [
            grant.team_id for grant in self.team_grants.list_for_user(user_id, organization_id)
        ]

    def accessible_project_ids(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[uuid.UUID]:
        return [
            grant.project_id
            for grant in self.project_grants.list_for_user(user_id, organization_id)
        ]

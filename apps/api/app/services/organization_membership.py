import uuid

from app.core.exceptions import ConflictError, DomainValidationError, ForbiddenError, NotFoundError
from app.models.enums import MembershipStatus, UserRole
from app.models.organization_membership import OrganizationMembership
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.repositories.user import UserRepository
from app.schemas.organization_membership import MembershipCreate

_ESCALATED_ROLES = frozenset({UserRole.OWNER, UserRole.ADMIN})


class OrganizationMembershipService:
    """Add/list/change-role/revoke/reactivate a member within one
    Organization (Phase 12) — the per-organization equivalent of Phase 10's
    UserService.change_role, including the same Owner-escalation and
    last-Owner invariants, now scoped by organization_id rather than
    global. See docs/adr/0012-organizations-multi-tenancy.md.

    change_role/revoke take an explicit acting_membership parameter for
    the same reason Phase 10's UserService.change_role took acting_user —
    the check IS the business rule (who may grant/revoke an Owner/Admin
    role), not audit logging.

    Phase 15: the last-owner invariant itself is now enforced by an atomic
    guarded UPDATE (OrganizationMembershipRepository.change_role_if_safe/
    revoke_if_safe), not a separate read-then-write — see those methods'
    docstrings and docs/adr/0015-last-owner-invariant.md for the
    concurrency race this closes. The escalation check below (who may
    touch an Owner/Admin role) stays a plain read against
    acting_membership, which is resolved fresh per-request by
    get_current_membership and carries no race of its own.
    """

    def __init__(
        self, repository: OrganizationMembershipRepository, user_repository: UserRepository
    ) -> None:
        self.repository = repository
        self.user_repository = user_repository

    def add_member(
        self, organization_id: uuid.UUID, data: MembershipCreate
    ) -> OrganizationMembership:
        user = self.user_repository.get_by_email(data.email)
        if user is None:
            raise NotFoundError("User", data.email)

        existing = self.repository.get_by_user_and_org(user.id, organization_id)
        if existing is not None:
            if existing.status == MembershipStatus.ACTIVE:
                raise ConflictError("This user is already a member of this organization.")
            raise ConflictError(
                "This user has a revoked membership in this organization — "
                "reactivate it instead of adding a new one."
            )

        membership = OrganizationMembership(
            user_id=user.id,
            organization_id=organization_id,
            role=data.role,
            status=MembershipStatus.ACTIVE,
        )
        return self.repository.add(membership)

    def list_for_org(
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[OrganizationMembership], int]:
        return self.repository.list_for_org(organization_id, limit=limit, offset=offset)

    def change_role(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        new_role: UserRole,
        *,
        acting_membership: OrganizationMembership,
    ) -> OrganizationMembership:
        membership = self._get_owned(organization_id, user_id)

        if (
            membership.role in _ESCALATED_ROLES or new_role in _ESCALATED_ROLES
        ) and acting_membership.role != UserRole.OWNER:
            raise ForbiddenError("Only an Owner can grant or change an Owner/Admin role.")

        if not self.repository.change_role_if_safe(organization_id, user_id, new_role):
            raise DomainValidationError(
                "Cannot demote the last remaining Owner of this organization."
            )
        self.repository.session.refresh(membership)
        return membership

    def revoke(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> OrganizationMembership:
        membership = self._get_owned(organization_id, user_id)

        if not self.repository.revoke_if_safe(organization_id, user_id):
            raise DomainValidationError(
                "Cannot revoke the last remaining Owner of this organization."
            )
        self.repository.session.refresh(membership)
        return membership

    def reactivate(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> OrganizationMembership:
        membership = self._get_owned(organization_id, user_id)
        membership.status = MembershipStatus.ACTIVE
        self.repository.session.flush()
        return membership

    def _get_owned(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMembership:
        membership = self.repository.get_by_user_and_org(user_id, organization_id)
        if membership is None:
            raise NotFoundError("OrganizationMembership", user_id)
        return membership

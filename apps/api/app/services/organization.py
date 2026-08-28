import uuid

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.models.enums import MembershipStatus, UserRole
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


class OrganizationService:
    """Organization lifecycle (Phase 12; deactivation hardened + reactivation
    added Phase 31) — create/retrieve/update/list-mine/deactivate/reactivate.
    No hard delete (see Organization.is_active's docstring) and no billing/
    subscription concept anywhere in this phase. See
    docs/adr/0012-organizations-multi-tenancy.md and
    docs/adr/0031-organization-deactivation-safety.md.
    """

    def __init__(
        self,
        repository: OrganizationRepository,
        membership_repository: OrganizationMembershipRepository,
    ) -> None:
        self.repository = repository
        self.membership_repository = membership_repository

    def create(self, data: OrganizationCreate, *, creator: User) -> Organization:
        """Creates the organization AND the creator's own Owner membership
        in the same call — an organization with zero Owners could never
        satisfy MEMBERSHIP_MANAGE's own guard (see
        OrganizationMembershipService), so it must never exist even
        momentarily."""
        if self.repository.get_by_slug(data.slug) is not None:
            raise ConflictError(f"An organization with slug '{data.slug}' already exists.")

        organization = self.repository.add(
            Organization(name=data.name, slug=data.slug, is_active=True)
        )
        self.membership_repository.add(
            OrganizationMembership(
                user_id=creator.id,
                organization_id=organization.id,
                role=UserRole.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )
        return organization

    def get(self, organization_id: uuid.UUID) -> Organization:
        organization = self.repository.get(organization_id)
        if organization is None:
            raise NotFoundError("Organization", organization_id)
        return organization

    def list_mine(self, user_id: uuid.UUID) -> list[Organization]:
        memberships = self.membership_repository.list_active_for_user(user_id)
        organization_ids = [m.organization_id for m in memberships]
        return self.repository.list_by_ids(organization_ids)

    def update(self, organization_id: uuid.UUID, data: OrganizationUpdate) -> Organization:
        organization = self.get(organization_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(organization, field, value)
        self.repository.session.flush()
        return organization

    def deactivate(self, organization_id: uuid.UUID) -> Organization:
        """Soft-delete only — see Organization.is_active's docstring. Once
        deactivated, get_current_membership (app/api/deps.py) denies every
        member's access on their very next request, and switch_organization
        (app/services/auth.py) treats it as not-found.

        Phase 31 safety guard: refuses (DomainValidationError -> 422) unless
        the organization still has at least one OTHER active Owner besides
        the actor — i.e. >= 2 active Owners total — so a soft-deactivated
        organization always has an Owner able to reactivate it via
        POST /api/v1/organizations/{id}/reactivate. The check is an atomic
        guarded UPDATE (OrganizationRepository.deactivate_if_safe), not a
        read-then-write, so a concurrent Owner-removing mutation can't race
        past it. See docs/adr/0031-organization-deactivation-safety.md.

        Nothing but the `is_active` flag is touched — memberships, teams,
        projects, allocations, scenarios, and snapshots are all left
        exactly as they were (no cascade)."""
        organization = self.get(organization_id)
        if not self.repository.deactivate_if_safe(organization_id):
            raise DomainValidationError(
                "This organization cannot be deactivated while it has only one "
                "active Owner — deactivation would leave no one able to reactivate "
                "it. Add a second Owner first, then try again."
            )
        self.repository.session.refresh(organization)
        return organization

    def reactivate(self, organization_id: uuid.UUID) -> Organization:
        """Restores `is_active=True` on a soft-deactivated organization —
        the exact inverse of deactivate()'s single-flag flip. Never
        recreates or mutates any membership, project, scenario, or other
        row; organization identity (id, slug) and every relationship are
        preserved untouched. Idempotent: an already-active organization is
        returned unchanged.

        Authorization for this operation is resolved by the route directly
        against the caller's own membership in the TARGET organization
        (not the session's active-organization context, which a
        deactivated org cannot provide) — see reactivate_organization in
        app/api/v1/organizations.py."""
        organization = self.get(organization_id)
        if not organization.is_active:
            organization.is_active = True
            self.repository.session.flush()
        return organization

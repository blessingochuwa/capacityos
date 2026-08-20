import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import MembershipStatus, UserRole
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


class OrganizationService:
    """Organization lifecycle (Phase 12) — create/retrieve/update/list-
    mine/deactivate. No hard delete (see Organization.is_active's
    docstring) and no billing/subscription concept anywhere in this phase.
    See docs/adr/0012-organizations-multi-tenancy.md.
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
        member's access on their very next request, and the organization
        stops appearing in list_mine (list_by_ids still returns it directly
        by id for an admin who already has it open, but list_active
        wouldn't)."""
        organization = self.get(organization_id)
        organization.is_active = False
        self.repository.session.flush()
        return organization

import uuid

from sqlalchemy import func, select

from app.models.enums import MembershipStatus, UserRole
from app.models.organization_membership import OrganizationMembership
from app.repositories.base import BaseRepository


class OrganizationMembershipRepository(BaseRepository[OrganizationMembership]):
    """Scoped by (user_id, organization_id) pairs rather than a single
    organization_id column filter — this table IS the membership boundary
    other org-scoped repositories filter against, not itself filtered by
    one. Replaces Phase 10's UserRepository.count_by_role, which was a
    fully unscoped `SELECT COUNT(*) ... WHERE role=Owner` — the "at least
    one active Owner" invariant is now per-organization (Phase 12)."""

    model = OrganizationMembership

    def get_by_user_and_org(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> OrganizationMembership | None:
        return self.session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.organization_id == organization_id,
            )
        )

    def list_active_for_user(self, user_id: uuid.UUID) -> list[OrganizationMembership]:
        """Drives login's auto-select-if-exactly-one-membership behavior
        and populates CurrentUser.organizations for the frontend switcher."""
        return list(
            self.session.scalars(
                select(OrganizationMembership).where(
                    OrganizationMembership.user_id == user_id,
                    OrganizationMembership.status == MembershipStatus.ACTIVE,
                )
            )
        )

    def list_for_org(
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[OrganizationMembership], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(OrganizationMembership.organization_id == organization_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(OrganizationMembership)
                .where(OrganizationMembership.organization_id == organization_id)
                .order_by(OrganizationMembership.created_at)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def count_active_owners(self, organization_id: uuid.UUID) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(
                    OrganizationMembership.organization_id == organization_id,
                    OrganizationMembership.role == UserRole.OWNER,
                    OrganizationMembership.status == MembershipStatus.ACTIVE,
                )
            )
            or 0
        )

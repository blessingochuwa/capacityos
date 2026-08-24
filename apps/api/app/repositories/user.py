import uuid

from sqlalchemy import CursorResult, func, or_, select, update
from sqlalchemy.orm import aliased

from app.models.base import utcnow
from app.models.enums import MembershipStatus, UserRole, UserStatus
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """count_by_role was removed in Phase 12 — the "at least one active
    Owner" invariant moved off User (role is no longer a column here) onto
    OrganizationMembershipRepository.count_active_owners, since it is now
    a per-organization invariant rather than a global one. See
    docs/adr/0012-organizations-multi-tenancy.md.

    disable_if_safe (Phase 15) is the one place this repository reaches
    into OrganizationMembership — a deliberate, narrow exception: closing
    the account-deactivation gap (docs/adr/0015-last-owner-invariant.md)
    atomically requires the guard subquery to live in the SAME UPDATE
    statement that flips User.status, so it cannot be split into a
    separate read against OrganizationMembershipRepository without
    reopening the exact read-then-write race that method exists to
    close."""

    model = User

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def get_by_person_id(self, person_id: uuid.UUID) -> User | None:
        return self.session.scalar(select(User).where(User.person_id == person_id))

    def list_by_ids(self, user_ids: list[uuid.UUID]) -> list[User]:
        """Batched lookup for a known set of ids — one query, not one per
        id (CLAUDE.md §27). Used to resolve MembershipRead's email/
        display_name for a page of memberships."""
        if not user_ids:
            return []
        return list(self.session.scalars(select(User).where(User.id.in_(user_ids))))

    def list_filtered(
        self, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[User], int]:
        total = self.session.scalar(select(func.count()).select_from(User)) or 0
        items = list(
            self.session.scalars(select(User).order_by(User.email).limit(limit).offset(offset))
        )
        return items, total

    def disable_if_safe(self, user_id: uuid.UUID) -> bool:
        """Atomically disables a User, guarded by the Phase 15 last-owner
        invariant: blocked if this user holds an active Owner membership
        in an organization with no OTHER active-Owner-with-an-active-
        account. Evaluated as part of the same UPDATE (see
        OrganizationMembershipRepository.change_role_if_safe's docstring
        for why read-then-write is unsafe under concurrent requests) so a
        concurrent role change/revoke on the same user's last-Owner
        membership can't race this into leaving an organization
        ownerless.

        Returns False (zero rows updated) exactly when disabling would
        strand at least one organization without an active Owner. The
        caller already resolved the user to exist before calling this, so
        False is unambiguous. Returns True if the user was already
        disabled (idempotent) or if no organization is left ownerless."""
        member = aliased(OrganizationMembership)
        other_owner = aliased(OrganizationMembership)
        other_owner_user = aliased(User)

        another_active_owner_exists = (
            select(other_owner.id)
            .join(other_owner_user, other_owner_user.id == other_owner.user_id)
            .where(
                other_owner.organization_id == member.organization_id,
                other_owner.role == UserRole.OWNER,
                other_owner.status == MembershipStatus.ACTIVE,
                other_owner_user.status == UserStatus.ACTIVE,
                other_owner.user_id != user_id,
            )
            .exists()
        )
        would_orphan_an_organization = (
            select(member.id)
            .where(
                member.user_id == user_id,
                member.role == UserRole.OWNER,
                member.status == MembershipStatus.ACTIVE,
                ~another_active_owner_exists,
            )
            .exists()
        )
        stmt = (
            update(User)
            .where(
                User.id == user_id,
                or_(User.status == UserStatus.DISABLED, ~would_orphan_an_organization),
            )
            .values(status=UserStatus.DISABLED, updated_at=utcnow())
        )
        result = self.session.execute(stmt)
        assert isinstance(result, CursorResult)  # noqa: S101 — an UPDATE always returns one
        return result.rowcount == 1

import uuid

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import aliased

from app.models.base import utcnow
from app.models.enums import MembershipStatus, UserRole, UserStatus
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """NOT organization-scoped itself — Organization is the tenant root
    every other org-owned table's organization_id points at, so its own
    `get`/`list` (inherited from BaseRepository unchanged) are legitimately
    unscoped: resolving "does this organization exist" is exactly how every
    other scoping check starts.

    Phase 31: `deactivate_if_safe` reaches into OrganizationMembership/User
    for its guard subquery — the same deliberate, narrow exception
    `UserRepository.disable_if_safe` already makes (Phase 15), and for the
    same reason: the guard MUST be evaluated inside the same UPDATE that
    flips `is_active`, or two concurrent requests (one deactivating, one
    demoting/revoking the other Owner) could each pass a stale check and
    strand the organization with no active Owner able to reactivate it.
    See docs/adr/0031-organization-deactivation-safety.md.
    """

    model = Organization

    def get_by_slug(self, slug: str) -> Organization | None:
        return self.session.scalar(select(Organization).where(Organization.slug == slug))

    def list_by_ids(self, organization_ids: list[uuid.UUID]) -> list[Organization]:
        """Batched lookup for a known set of ids — one query, not one per
        id (CLAUDE.md §27). Used to build MeRead's organizations list from
        a user's memberships."""
        if not organization_ids:
            return []
        return list(
            self.session.scalars(
                select(Organization).where(Organization.id.in_(organization_ids))
            )
        )

    def list_active(self, *, limit: int = 100, offset: int = 0) -> tuple[list[Organization], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(Organization)
                .where(Organization.is_active.is_(True))
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(Organization)
                .where(Organization.is_active.is_(True))
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def deactivate_if_safe(self, organization_id: uuid.UUID) -> bool:
        """Atomically sets `is_active=False`, guarded by the Phase 31
        safety invariant re-evaluated AT WRITE TIME: an organization may
        only be deactivated while it still has at least ONE OTHER active
        Owner (an `OrganizationMembership` with role=Owner, status=Active,
        whose linked `User` is also Active) besides — or as well as — the
        actor, i.e. **two or more** active Owners in total. The actor is
        always an Owner (the route is `ORGANIZATION_MANAGE`-gated), so
        `>= 2` is exactly "there is another Owner who could reactivate
        this".

        Folding the count into the UPDATE's own WHERE clause (rather than
        a separate SELECT-then-decide) is what makes it race-safe: SQLite
        (like PostgreSQL) serializes writers, so a concurrent role-change/
        revoke on the other Owner's membership either commits before this
        UPDATE — which then re-evaluates the subquery fresh and sees only
        one Owner, so `rowcount == 0` — or after it, in which case that
        operation's own Phase 15 guard sees the (still active) org's two
        Owners. Either ordering preserves the invariant. Mirrors
        `OrganizationMembershipRepository.change_role_if_safe` exactly.

        Returns False (zero rows updated) exactly when the guard blocked
        the write — the caller has already resolved the organization to
        exist (and to be the caller's own active org) before calling this,
        so False is unambiguous. Idempotent for an org that already has
        `>= 2` Owners even if it were already inactive (the route can't
        reach this for an inactive org, but the service contract stays
        clean)."""
        member = aliased(OrganizationMembership)
        member_user = aliased(User)
        active_owner_count = (
            select(func.count())
            .select_from(member)
            .join(member_user, member_user.id == member.user_id)
            .where(
                member.organization_id == organization_id,
                member.role == UserRole.OWNER,
                member.status == MembershipStatus.ACTIVE,
                member_user.status == UserStatus.ACTIVE,
            )
            .scalar_subquery()
        )
        stmt = (
            update(Organization)
            .where(Organization.id == organization_id, active_owner_count >= 2)
            .values(is_active=False, updated_at=utcnow())
        )
        result = self.session.execute(stmt)
        assert isinstance(result, CursorResult)  # noqa: S101 — an UPDATE always returns one
        return result.rowcount == 1

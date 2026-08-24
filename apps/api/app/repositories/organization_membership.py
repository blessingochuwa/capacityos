import uuid

from sqlalchemy import CursorResult, ScalarSelect, func, or_, select, update
from sqlalchemy.orm import aliased

from app.models.base import utcnow
from app.models.enums import MembershipStatus, UserRole, UserStatus
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.base import BaseRepository


class OrganizationMembershipRepository(BaseRepository[OrganizationMembership]):
    """Scoped by (user_id, organization_id) pairs rather than a single
    organization_id column filter — this table IS the membership boundary
    other org-scoped repositories filter against, not itself filtered by
    one. Replaces Phase 10's UserRepository.count_by_role, which was a
    fully unscoped `SELECT COUNT(*) ... WHERE role=Owner` — the "at least
    one active Owner" invariant is now per-organization (Phase 12).

    Phase 15: "active Owner" here means an active OrganizationMembership
    (role=Owner, status=Active) whose linked User is ALSO active —
    AuthService.resolve_session/login (app/services/auth.py) already
    refuse to authenticate a disabled User outright, so an Owner
    membership pointing at a disabled account cannot actually exercise
    Owner authority; counting it would make the last-owner invariant
    vacuous for the account-deactivation path. See
    docs/adr/0015-last-owner-invariant.md."""

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
                .join(User, User.id == OrganizationMembership.user_id)
                .where(
                    OrganizationMembership.organization_id == organization_id,
                    OrganizationMembership.role == UserRole.OWNER,
                    OrganizationMembership.status == MembershipStatus.ACTIVE,
                    User.status == UserStatus.ACTIVE,
                )
            )
            or 0
        )

    def _active_owner_count_subquery(self, organization_id: uuid.UUID) -> ScalarSelect[int]:
        """A correlated-at-execution-time count, used as a WHERE-clause
        guard on the atomic UPDATEs below — NOT run as a separate read
        beforehand. Evaluating the count as part of the same write
        statement (rather than read-then-write) is what closes the race
        two concurrent requests could otherwise exploit: see
        change_role_if_safe's docstring and
        docs/adr/0015-last-owner-invariant.md."""
        m = aliased(OrganizationMembership)
        u = aliased(User)
        return (
            select(func.count())
            .select_from(m)
            .join(u, u.id == m.user_id)
            .where(
                m.organization_id == organization_id,
                m.role == UserRole.OWNER,
                m.status == MembershipStatus.ACTIVE,
                u.status == UserStatus.ACTIVE,
            )
            .scalar_subquery()
        )

    def change_role_if_safe(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, new_role: UserRole
    ) -> bool:
        """Atomically changes one membership's role, guarded by the
        last-owner invariant re-evaluated AT WRITE TIME. A plain
        "SELECT count, then decide, then UPDATE" (the pre-Phase-15 shape)
        is unsafe: two concurrent requests can each read count=2 before
        either writes, and both then proceed, leaving zero Owners. Folding
        the count into the UPDATE's own WHERE clause closes that race —
        SQLite (like PostgreSQL) serializes writers, so whichever request's
        UPDATE actually executes first commits against a guard value that
        is still accurate, and the second one's UPDATE (blocked until the
        first commits, per app/core/database.py's busy_timeout) then
        re-evaluates the SAME subquery fresh, seeing the first request's
        already-committed change.

        Returns False (zero rows updated) exactly when this membership is
        currently the organization's sole active Owner — the caller
        already resolved the membership to exist (404 otherwise) before
        calling this, so False is unambiguous: it can only mean the
        invariant blocked the write, never "no such row." Returns True
        for every other case, including a no-op role "change" to the same
        role — matching the pre-Phase-15 behavior of always succeeding
        when the actor isn't the last Owner."""
        guard_count = self._active_owner_count_subquery(organization_id)
        stmt = (
            update(OrganizationMembership)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.organization_id == organization_id,
                or_(OrganizationMembership.role != UserRole.OWNER, guard_count > 1),
            )
            .values(role=new_role, updated_at=utcnow())
        )
        result = self.session.execute(stmt)
        assert isinstance(result, CursorResult)  # noqa: S101 — an UPDATE always returns one
        return result.rowcount == 1

    def revoke_if_safe(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Revoke counterpart to change_role_if_safe above — same atomic
        guard, same race closed. Returns False exactly when this
        membership is an active Owner membership and is the organization's
        sole active Owner. Revoking an already-revoked membership, or one
        that was never an Owner, always succeeds (matches pre-Phase-15
        behavior)."""
        guard_count = self._active_owner_count_subquery(organization_id)
        stmt = (
            update(OrganizationMembership)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.organization_id == organization_id,
                or_(
                    OrganizationMembership.role != UserRole.OWNER,
                    OrganizationMembership.status != MembershipStatus.ACTIVE,
                    guard_count > 1,
                ),
            )
            .values(status=MembershipStatus.REVOKED, updated_at=utcnow())
        )
        result = self.session.execute(stmt)
        assert isinstance(result, CursorResult)  # noqa: S101 — an UPDATE always returns one
        return result.rowcount == 1

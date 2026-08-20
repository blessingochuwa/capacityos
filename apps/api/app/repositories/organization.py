import uuid

from sqlalchemy import func, select

from app.models.organization import Organization
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """NOT organization-scoped itself — Organization is the tenant root
    every other org-owned table's organization_id points at, so its own
    `get`/`list` (inherited from BaseRepository unchanged) are legitimately
    unscoped: resolving "does this organization exist" is exactly how every
    other scoping check starts."""

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

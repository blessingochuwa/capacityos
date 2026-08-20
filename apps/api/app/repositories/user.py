import uuid

from sqlalchemy import func, select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """count_by_role was removed in Phase 12 — the "at least one active
    Owner" invariant moved off User (role is no longer a column here) onto
    OrganizationMembershipRepository.count_active_owners, since it is now
    a per-organization invariant rather than a global one. See
    docs/adr/0012-organizations-multi-tenancy.md."""

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

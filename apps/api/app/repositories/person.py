import uuid

from sqlalchemy import func, select

from app.models.person import Person
from app.repositories.base import BaseRepository


class PersonRepository(BaseRepository[Person]):
    """Organization-scoped (Phase 12) — every lookup requires
    organization_id, deliberately shadowing BaseRepository.get/list's
    unscoped signatures so every pre-Phase-12 call site becomes a type
    error rather than a silent cross-tenant leak. This is the reference
    pattern every other organization-owned entity's repository follows —
    see docs/adr/0012-organizations-multi-tenancy.md."""

    model = Person

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> Person | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(Person).where(Person.id == id_, Person.organization_id == organization_id)
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[Person], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(Person)
                .where(Person.organization_id == organization_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(Person)
                .where(Person.organization_id == organization_id)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def get_by_email(self, email: str, organization_id: uuid.UUID) -> Person | None:
        return self.session.scalar(
            select(Person).where(
                Person.email == email, Person.organization_id == organization_id
            )
        )

    def list_by_ids(self, person_ids: list[uuid.UUID], organization_id: uuid.UUID) -> list[Person]:
        """Batched lookup for a known set of ids — one query, not one per id
        (CLAUDE.md §27). Used by scenario calculation to label affected
        people (app/services/scenario_calculation.py)."""
        if not person_ids:
            return []
        return list(
            self.session.scalars(
                select(Person).where(
                    Person.id.in_(person_ids), Person.organization_id == organization_id
                )
            )
        )

    def list_by_emails(self, emails: list[str], organization_id: uuid.UUID) -> list[Person]:
        """Batched lookup for Phase 6 import identity resolution."""
        if not emails:
            return []
        return list(
            self.session.scalars(
                select(Person).where(
                    Person.email.in_(emails), Person.organization_id == organization_id
                )
            )
        )
